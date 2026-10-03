"""Verified Apple subscription reconciliation, isolated from Stripe and AI.

Only AppleGateway results enter reconciliation. Client arguments never contain
plan/status/user authority. API reads occur before the short DB transaction.
Original ownership and notification deduplication commit with entitlement state.
"""
from datetime import datetime, timezone, timedelta
import logging
from uuid import UUID, uuid4

from services.apple_gateway import AppleBillingError, AppleConfig, AppleGateway
from services.billing_entitlements import effective_entitlement

logger = logging.getLogger(__name__)
PRODUCTS = {'nova.pro.monthly': 'pro', 'nova.max.monthly': 'max'}


def value(obj, key, default=None):
    found = getattr(obj, key, default)
    return getattr(found, 'value', found)


def timestamp(ms):
    if type(ms) is not int or ms <= 0:
        raise AppleBillingError('verification_failed')
    try:
        return datetime.fromtimestamp(ms / 1000, timezone.utc).replace(tzinfo=None)
    except (ValueError, OverflowError, OSError):
        raise AppleBillingError('verification_failed') from None


def identity(raw):
    if not isinstance(raw, str) or not raw.isascii() or not raw.isdigit() or not 1 <= len(raw) <= 64:
        raise AppleBillingError('verification_failed')
    return raw


def account_token(raw):
    try:
        return str(UUID(str(raw)))
    except (ValueError, TypeError, AttributeError):
        raise AppleBillingError('account_token_required') from None


class AppleBilling:
    def __init__(self, get_db, postgres=False, gateway=None):
        self.get_db, self.postgres = get_db, postgres
        self.gateway = gateway  # Lazy: Stripe remains usable when Apple is unconfigured.

    def _gateway(self):
        if self.gateway is None:
            self.gateway = AppleGateway(AppleConfig.load())
        return self.gateway

    def _begin(self, db):
        if not self.postgres:
            db.execute('BEGIN IMMEDIATE')

    def _locked_owner(self, db, original):
        return db.execute('SELECT * FROM apple_original_transactions WHERE original_transaction_id=?'
                          + (' FOR UPDATE' if self.postgres else ''), (original,)).fetchone()

    def issue_account_token(self, user_id):
        db = self.get_db()
        try:
            self._begin(db)
            db.execute('''INSERT INTO apple_account_tokens(user_id, app_account_token) VALUES(?, ?)
                          ON CONFLICT(user_id) DO NOTHING''', (user_id, str(uuid4())))
            token = db.execute('SELECT app_account_token FROM apple_account_tokens WHERE user_id=?',
                               (user_id,)).fetchone()['app_account_token']
            db.commit()
            return {'ok': True, 'app_account_token': token}
        except Exception:
            db.rollback()
            raise AppleBillingError('storage_unavailable') from None
        finally:
            db.close()

    def _check_transaction(self, tx):
        config = self._gateway().config
        if value(tx, 'bundleId') != config.bundle_id or value(tx, 'environment') != config.environment:
            raise AppleBillingError('verification_failed')
        if value(tx, 'type') != 'Auto-Renewable Subscription':
            raise AppleBillingError('verification_failed')
        # Family sharing needs an explicit separate account-ownership design.
        if value(tx, 'inAppOwnershipType') != 'PURCHASED':
            raise AppleBillingError('verification_failed')
        identity(value(tx, 'transactionId'))
        identity(value(tx, 'originalTransactionId'))
        signed = timestamp(value(tx, 'signedDate'))
        if signed > datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=5):
            raise AppleBillingError('verification_failed')

    def _current(self, presented):
        gateway = self._gateway()
        self._check_transaction(presented)
        original = value(presented, 'originalTransactionId')
        response = gateway.statuses(value(presented, 'transactionId'))
        if (value(response, 'bundleId') != gateway.config.bundle_id
                or value(response, 'environment') != gateway.config.environment
                or (gateway.config.environment == 'Production' and value(response, 'appAppleId') != gateway.config.app_id)):
            raise AppleBillingError('verification_failed')
        candidates = []
        for group in response.data or []:
            for item in group.lastTransactions or []:
                if value(item, 'originalTransactionId') != original:
                    continue
                tx = gateway.transaction(item.signedTransactionInfo)
                renewal = gateway.renewal(item.signedRenewalInfo)
                self._check_transaction(tx)
                if (value(tx, 'originalTransactionId') != original
                        or value(renewal, 'originalTransactionId') != original
                        or value(renewal, 'environment') != gateway.config.environment):
                    raise AppleBillingError('verification_failed')
                signed = max(timestamp(value(tx, 'signedDate')), timestamp(value(renewal, 'signedDate')))
                if signed > datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=5):
                    raise AppleBillingError('verification_failed')
                candidates.append((signed, tx, renewal, value(item, 'status')))
        # A single lineage must have one authoritative last transaction. Fail closed
        # rather than guessing across malformed/conflicting provider state.
        if len(candidates) != 1:
            raise AppleBillingError('verification_failed')
        signed, tx, renewal, status = candidates[0]
        product = value(tx, 'productId')
        plan = PRODUCTS.get(product)
        start, end = timestamp(value(tx, 'purchaseDate')), timestamp(value(tx, 'expiresDate'))
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        revoked = value(tx, 'revocationDate')
        state = {1: 'active', 2: 'expired', 3: 'billing_retry', 4: 'grace', 5: 'revoked'}.get(status, 'unknown')
        if revoked is not None:
            revoked = timestamp(revoked)
            state = 'revoked'
        if value(tx, 'isUpgraded'):
            state = 'superseded'
        access_end = end
        if state == 'grace':
            grace = value(renewal, 'gracePeriodExpiresDate')
            access_end = timestamp(grace) if grace else end
        active = bool(plan and state in {'active', 'grace'} and not revoked and start <= now < access_end)
        if not plan:
            state = 'unsupported_product'
        elif state in {'active', 'grace'} and access_end <= now:
            state = 'expired'
        token = value(tx, 'appAccountToken')
        return dict(original=original, transaction_id=value(tx, 'transactionId'), product=product,
                    plan=plan or 'none', state=state, status='active' if active else 'inactive',
                    signed=signed, start=start, end=access_end, renewal_at=end, revoked=revoked,
                    token=account_token(token) if token else None, environment=gateway.config.environment,
                    auto_renews=value(renewal, 'autoRenewStatus') if value(renewal, 'autoRenewStatus') in (0, 1) else None,
                    cancel=1 if value(renewal, 'autoRenewStatus') == 0 else 0)

    def sync(self, user_id, signed_transaction):
        gateway = self._gateway()
        presented = gateway.transaction(signed_transaction)
        self._check_transaction(presented)
        if value(presented, 'productId') not in PRODUCTS:
            raise AppleBillingError('unsupported_product')
        snapshot = self._current(presented)
        return self._reconcile(snapshot, user_id=user_id)

    def notification(self, signed_payload):
        gateway = self._gateway()
        note = gateway.notification(signed_payload)
        try:
            notification_id = str(UUID(str(value(note, 'notificationUUID'))))
        except (ValueError, TypeError):
            raise AppleBillingError('verification_failed') from None
        signed = timestamp(value(note, 'signedDate'))
        data = getattr(note, 'data', None)
        if (data is None or value(data, 'bundleId') != gateway.config.bundle_id
                or value(data, 'environment') != gateway.config.environment
                or (gateway.config.environment == 'Production' and value(data, 'appAppleId') != gateway.config.app_id)):
            raise AppleBillingError('verification_failed')
        kind = value(note, 'notificationType')
        if not isinstance(kind, str) or not 1 <= len(kind) <= 100:
            raise AppleBillingError('verification_failed')
        if signed > datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=5):
            raise AppleBillingError('verification_failed')
        # Fast duplicate check occurs only AFTER signature and identity validation.
        db = self.get_db()
        try:
            duplicate = db.execute('SELECT id FROM apple_notifications WHERE notification_uuid=?',
                                   (notification_id,)).fetchone()
        finally:
            db.close()
        if duplicate:
            return {'ok': True, 'duplicate': True}
        notification = (notification_id, signed, kind, gateway.config.environment)
        if kind == 'TEST':
            return self._reconcile(None, notification=notification)
        payload = value(data, 'signedTransactionInfo')
        if not payload:
            raise AppleBillingError('verification_failed')
        presented = gateway.transaction(payload)
        # Every lifecycle event refreshes current API state: a delayed refund of an
        # old renewal must not revoke a newer valid purchase. No event=>active rule.
        snapshot = self._current(presented)
        return self._reconcile(snapshot, notification=notification)

    def _reconcile(self, state, user_id=None, notification=None):
        db = self.get_db()
        try:
            self._begin(db)
            if notification:
                nid, signed, kind, environment = notification
                inserted = db.execute('''INSERT INTO apple_notifications
                    (notification_uuid, original_transaction_id, signed_at, notification_type, environment)
                    VALUES (?, ?, ?, ?, ?) ON CONFLICT(notification_uuid) DO NOTHING''',
                    (nid, state['original'] if state else None, signed.isoformat(' '), kind, environment))
                if inserted.rowcount == 0:
                    db.commit()
                    return {'ok': True, 'duplicate': True}
            if state is None:
                outcome = 'test'
            else:
                owner = self._locked_owner(db, state['original'])
                token_row = (db.execute('SELECT user_id FROM apple_account_tokens WHERE app_account_token=?',
                                       (state['token'],)).fetchone() if state['token'] else None)
                token_user = token_row['user_id'] if token_row else None
                if owner:
                    if ((user_id is not None and owner['user_id'] != user_id)
                            or (state['token'] and token_user != owner['user_id'])):
                        raise AppleBillingError('ownership_conflict')
                    user_id = owner['user_id']
                else:
                    if user_id is not None and token_user != user_id:
                        raise AppleBillingError('account_token_required')
                    user_id = token_user
                if user_id is None:
                    # Notifications without a Nova account binding grant nobody access.
                    # A later authenticated restore fetches current Apple status again.
                    outcome = 'unbound'
                else:
                    db.execute('''INSERT INTO apple_original_transactions
                        (original_transaction_id, user_id, environment) VALUES (?, ?, ?)
                        ON CONFLICT(original_transaction_id) DO NOTHING''',
                        (state['original'], user_id, state['environment']))
                    owner = self._locked_owner(db, state['original'])
                    if owner['user_id'] != user_id or owner['environment'] not in ('', state['environment']):
                        raise AppleBillingError('ownership_conflict')
                    previous = owner['last_signed_at']
                    if isinstance(previous, str):
                        previous = datetime.fromisoformat(previous)
                    if previous and previous >= state['signed']:
                        outcome = 'stale'
                    else:
                        self._write_state(db, user_id, state)
                        outcome = 'reconciled'
            if notification:
                db.execute('''UPDATE apple_notifications SET processed_at=CURRENT_TIMESTAMP, outcome=?
                              WHERE notification_uuid=?''', (outcome, notification[0]))
            rows = db.execute('SELECT * FROM subscriptions WHERE user_id=?', (user_id,)).fetchall() if user_id else []
            effective = effective_entitlement(rows)
            db.commit()
            logger.info('apple_billing outcome=%s', outcome)
            if notification:
                return {'ok': True, 'duplicate': False, 'outcome': outcome}
            return self._response(effective, rows, outcome)
        except AppleBillingError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise AppleBillingError('storage_unavailable') from None
        finally:
            db.close()

    def _write_state(self, db, user_id, s):
        stamp = lambda v: v.isoformat(' ') if v is not None else None
        tx = db.execute('''INSERT INTO apple_transactions
            (user_id, transaction_id, original_transaction_id, product_id, plan, status,
             purchased_at, expires_at, revoked_at, environment, signed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(transaction_id) DO UPDATE SET product_id=excluded.product_id,
                plan=excluded.plan, status=excluded.status, expires_at=excluded.expires_at,
                revoked_at=excluded.revoked_at, signed_at=excluded.signed_at, updated_at=CURRENT_TIMESTAMP
            WHERE apple_transactions.user_id=excluded.user_id
              AND apple_transactions.original_transaction_id=excluded.original_transaction_id
              AND apple_transactions.environment=excluded.environment''',
            (user_id,s['transaction_id'],s['original'],s['product'],s['plan'],s['state'],
             stamp(s['start']),stamp(s['renewal_at']),stamp(s['revoked']),s['environment'],stamp(s['signed'])))
        if tx.rowcount == 0:
            raise AppleBillingError('ownership_conflict')
        result = db.execute('''INSERT INTO subscriptions
            (user_id,plan,status,provider,provider_subscription_id,current_period_start,current_period_end,
             cancel_at_period_end,verified_at,apple_environment,apple_state,apple_renewal_at,apple_auto_renews)
            VALUES (?, ?, ?, 'apple', ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?)
            ON CONFLICT(provider,provider_subscription_id)
            WHERE provider_subscription_id IS NOT NULL AND provider_subscription_id <> ''
            DO UPDATE SET plan=excluded.plan,status=excluded.status,current_period_start=excluded.current_period_start,
                current_period_end=excluded.current_period_end,cancel_at_period_end=excluded.cancel_at_period_end,
                verified_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP,
                apple_environment=excluded.apple_environment,apple_state=excluded.apple_state,
                apple_renewal_at=excluded.apple_renewal_at,apple_auto_renews=excluded.apple_auto_renews
            WHERE subscriptions.user_id=excluded.user_id''',
            (user_id,s['plan'],s['status'],s['original'],stamp(s['start']),stamp(s['end']),s['cancel'],
             s['environment'],s['state'],stamp(s['renewal_at']),s['auto_renews']))
        if result.rowcount == 0:
            raise AppleBillingError('ownership_conflict')
        db.execute('''UPDATE apple_original_transactions SET last_signed_at=?, environment=?
                      WHERE original_transaction_id=? AND user_id=?''',
                   (stamp(s['signed']),s['environment'],s['original'],user_id))

    @staticmethod
    def _response(effective, rows, outcome):
        def iso(v):
            if not v:
                return None
            if isinstance(v, str):
                v = datetime.fromisoformat(v)
            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)
            return v.isoformat()
        effective = dict(effective or {'plan':'none','status':'inactive','billing_source':None,'active_billing_sources':[]})
        for key in ('current_period_start', 'current_period_end'):
            effective[key] = iso(effective.get(key))
        def displayed_state(row):
            state = row['apple_state']
            expiry = iso(row['current_period_end'])
            if state in {'active', 'grace'} and expiry and datetime.fromisoformat(expiry) <= datetime.now(timezone.utc):
                return 'expired'
            return state
        apple = [{
            'plan': row['plan'], 'status': displayed_state(row), 'environment': row['apple_environment'],
            'expires_at': iso(row['current_period_end']), 'renewal_at': iso(row['apple_renewal_at']),
            'auto_renews': bool(row['apple_auto_renews']) if row['apple_auto_renews'] is not None else None,
        } for row in rows if row['provider'] == 'apple']
        sources = effective['active_billing_sources']
        return {'ok': True, 'sync': outcome, 'subscription': effective, 'apple_subscriptions': apple,
                'multiple_billing_sources': len(sources) > 1,
                'management': {'apple': 'https://apps.apple.com/account/subscriptions' if apple else None,
                               'web': '/create-portal-session' if 'web' in sources else None}}

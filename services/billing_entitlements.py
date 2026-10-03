"""Provider-neutral entitlement selection. No client payloads or network calls."""
from datetime import datetime, timezone
import os

TIERS = {'developer': 3, 'max': 2, 'pro': 1, 'paid': 1}


def _date(value):
    if not value:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def effective_entitlement(rows, now=None):
    now = now or datetime.now(timezone.utc)
    valid = []
    for item in rows:
        row = dict(item)
        if row['status'] != 'active' or row['plan'] not in TIERS:
            continue
        # Stripe remains webhook-authoritative, preserving current renewal behavior.
        # Apple must have a verified, unexpired period; placeholders grant nothing.
        if row['provider'] == 'apple':
            # Migration 2 rows carry an explicit verified environment. A sandbox
            # deployment must never leave paid sandbox access on production.
            if (row['plan'] not in {'pro', 'max'} or ('apple_environment' in row and
                    row['apple_environment'] != os.environ.get('APPLE_ENVIRONMENT', 'Production'))):
                continue
            try:
                end = _date(row.get('current_period_end'))
                start = _date(row.get('current_period_start'))
                if not row.get('verified_at') or not end or end <= now or (start and start > now):
                    continue
            except (TypeError, ValueError):
                continue
        valid.append(row)
    if not valid:
        return None
    # Equal tiers prefer existing web billing; stable ID breaks remaining ties.
    valid.sort(key=lambda r: (-TIERS[r['plan']], 0 if r['provider'] == 'stripe' else 1,
                             r['provider'], r['id']))
    selected = valid[0]
    public = {key: selected.get(key) for key in ('plan', 'status', 'current_period_start',
                                               'current_period_end', 'cancel_at_period_end')}
    source = lambda provider: {'stripe': 'web', 'apple': 'apple'}.get(provider)
    public['billing_source'] = source(selected['provider'])
    public['active_billing_sources'] = sorted({source(r['provider']) for r in valid if source(r['provider'])})
    return public


def get_effective_entitlement(get_db, user_id):
    db = get_db()
    try:
        return effective_entitlement(db.execute(
            'SELECT * FROM subscriptions WHERE user_id = ?', (user_id,)).fetchall())
    finally:
        db.close()


def get_stripe_subscription(get_db, user_id):
    db = get_db()
    try:
        row = db.execute("""SELECT * FROM subscriptions WHERE user_id = ? AND provider = 'stripe'
            AND COALESCE(provider_customer_id, '') <> ''
            ORDER BY CASE WHEN status = 'active' THEN 0 ELSE 1 END, updated_at DESC, id DESC""",
            (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        db.close()


def save_provider_subscription(get_db, user_id, plan, status, provider='stripe',
                               provider_customer_id='', provider_subscription_id='',
                               current_period_start=None, current_period_end=None):
    """Trusted server writer. Apple verification/reconciliation is intentionally absent.

    Apple placeholders may be stored inactive, but cannot grant access here.
    A future verified writer must bind ownership and update verified_at atomically.
    """
    if provider not in {'stripe', 'apple'} or plan not in TIERS:
        raise ValueError('Unsupported billing provider or plan')
    if not isinstance(provider_subscription_id, str) or not provider_subscription_id.strip():
        raise ValueError('A provider subscription identifier is required')
    if provider == 'apple' and status == 'active':
        raise ValueError('Apple activation requires server verification')
    db = get_db()
    try:
        # Unique index serializes concurrent retries. Ownership cannot be transferred.
        cursor = db.execute("""INSERT INTO subscriptions
            (user_id, plan, status, provider, provider_customer_id, provider_subscription_id,
             current_period_start, current_period_end)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (provider, provider_subscription_id)
            WHERE provider_subscription_id IS NOT NULL AND provider_subscription_id <> ''
            DO UPDATE SET plan=excluded.plan, status=excluded.status,
                provider_customer_id=excluded.provider_customer_id,
                current_period_start=excluded.current_period_start,
                current_period_end=excluded.current_period_end, updated_at=CURRENT_TIMESTAMP
            WHERE subscriptions.user_id=excluded.user_id""",
            (user_id, plan, status, provider, provider_customer_id, provider_subscription_id,
             current_period_start, current_period_end))
        if cursor.rowcount == 0:
            raise ValueError('Subscription already belongs to another account')
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

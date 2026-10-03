"""Apple integration tests: temporary databases, fake verified Apple responses only."""
import ast
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
from types import SimpleNamespace as Obj
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from flask import Flask, jsonify, request, session
from flask_login import LoginManager, UserMixin
import hmac

from services.apple_billing import AppleBilling
from services.apple_gateway import AppleBillingError, AppleConfig, AppleGateway
from services.apple_schema import migrate_apple_billing
from services.apple_routes import register_apple_billing
from services.billing_entitlements import get_effective_entitlement
import test_billing_foundation


class AppleTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_billing_foundation.BillingTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.migrate()
        migrate_apple_billing(self.fixture.db)
        self.connect = self.fixture.connect
        self.gateway = Mock()
        self.gateway.config = Obj(environment='Production',bundle_id='com.amirnyv.Nova',app_id=6817116419)
        self.service = AppleBilling(self.connect,gateway=self.gateway)
        self.token = self.service.issue_account_token(1)['app_account_token']
        now = int(datetime.now(timezone.utc).timestamp()*1000)
        self.tx = Obj(transactionId='10001',originalTransactionId='10000',productId='nova.pro.monthly',
            bundleId='com.amirnyv.Nova',environment='Production',type='Auto-Renewable Subscription',
            inAppOwnershipType='PURCHASED',appAccountToken=self.token,signedDate=now,
            purchaseDate=now-86400000,expiresDate=now+86400000,revocationDate=None,isUpgraded=False)
        self.renewal = Obj(originalTransactionId='10000',environment='Production',signedDate=now,
                           autoRenewStatus=1,gracePeriodExpiresDate=None)
        self.item = Obj(originalTransactionId='10000',signedTransactionInfo='current',signedRenewalInfo='renewal',status=1)
        self.gateway.transaction.return_value=self.tx
        self.gateway.renewal.return_value=self.renewal
        self.gateway.statuses.return_value=Obj(bundleId='com.amirnyv.Nova',environment='Production',
            appAppleId=6817116419,data=[Obj(lastTransactions=[self.item])])
        self.note=Obj(notificationUUID=str(uuid4()),signedDate=now,notificationType='DID_RENEW',
            data=Obj(bundleId='com.amirnyv.Nova',environment='Production',appAppleId=6817116419,signedTransactionInfo='notification-tx'))
        self.gateway.notification.return_value=self.note
        patcher=patch.dict(os.environ,{'APPLE_ENVIRONMENT':'Production'})
        patcher.start(); self.addCleanup(patcher.stop)

    def query(self, sql):
        return [dict(r) for r in self.fixture.db.execute(sql).fetchall()]

    def sync(self, user=1):
        return self.service.sync(user,'presented')

    def advance(self):
        self.tx.signedDate+=1
        self.renewal.signedDate+=1

    def test_pro_mapping_and_verified_pro(self):
        result=self.sync()
        self.assertEqual(result['apple_subscriptions'][0]['plan'],'pro')
        self.assertEqual(result['subscription']['plan'],'paid') # same-tier Stripe preference
        self.assertEqual(result['subscription']['active_billing_sources'],['apple','web'])
        self.assertTrue(result['multiple_billing_sources'])
        self.assertTrue(result['subscription']['current_period_end'] is None) # Stripe original fixture

    def test_max_mapping_apple_max_beats_stripe_pro(self):
        self.tx.productId='nova.max.monthly'
        result=self.sync()
        self.assertEqual(result['subscription']['plan'],'max')
        self.assertEqual(result['subscription']['billing_source'],'apple')
        self.assertIn('+00:00',result['subscription']['current_period_end'])

    def test_apple_pro_stripe_max(self):
        self.fixture.save(plan='max')
        self.assertEqual(self.sync()['subscription']['billing_source'],'web')
        self.assertEqual(self.sync()['subscription']['plan'],'max')

    def test_apple_only_and_revocation_fallback(self):
        self.tx.productId='nova.max.monthly'
        self.sync()
        self.advance();self.tx.revocationDate=self.tx.signedDate;self.item.status=5
        result=self.sync()
        self.assertEqual(result['subscription']['billing_source'],'web')
        self.assertEqual(result['apple_subscriptions'][0]['status'],'revoked')
        self.assertEqual(self.query("SELECT status FROM subscriptions WHERE provider='apple'")[0]['status'],'inactive')

    def test_apple_only_access(self):
        self.fixture.save(status='inactive')
        self.assertEqual(self.sync()['subscription']['billing_source'],'apple')

    def test_unknown_product_rejected(self):
        self.tx.productId='unknown'
        with self.assertRaisesRegex(AppleBillingError,'not supported'):
            self.sync()
        self.assertEqual(self.query("SELECT * FROM subscriptions WHERE provider='apple'"),[])

    def test_unknown_current_product_cannot_leave_old_max_active(self):
        self.tx.productId='nova.max.monthly';self.sync()
        old=deepcopy(self.tx)
        self.advance();self.tx.productId='unknown'
        self.gateway.transaction.side_effect=lambda payload: old if payload=='presented' else self.tx
        result=self.sync()
        self.assertEqual(result['subscription']['billing_source'],'web')
        self.assertEqual(result['apple_subscriptions'][0]['status'],'unsupported_product')

    def test_binding_cross_account_and_unbound_token_rejected(self):
        self.sync()
        with self.assertRaises(AppleBillingError) as conflict:
            self.sync(2)
        self.assertEqual(conflict.exception.code,'ownership_conflict')
        self.assertEqual(self.query('SELECT user_id FROM apple_original_transactions')[0]['user_id'],1)

    def test_missing_and_wrong_account_token_never_first_claim(self):
        for token in [None,str(uuid4()),self.service.issue_account_token(2)['app_account_token']]:
            self.tx.appAccountToken=token
            with self.assertRaises(AppleBillingError): self.sync()
        self.assertEqual(self.query('SELECT * FROM apple_original_transactions'),[])

    def test_duplicate_sync_and_stale_cannot_restore_revoked(self):
        first=deepcopy(self.tx);first_renewal=deepcopy(self.renewal)
        self.sync();self.assertEqual(self.sync()['sync'],'stale')
        self.advance();self.tx.revocationDate=self.tx.signedDate;self.item.status=5
        self.sync()
        self.gateway.transaction.return_value=first;self.gateway.renewal.return_value=first_renewal;self.item.status=1
        self.assertEqual(self.sync()['apple_subscriptions'][0]['status'],'revoked')
        self.assertEqual(len(self.query('SELECT * FROM apple_transactions')),1)

    def test_expiration_and_retry_do_not_grant(self):
        for status in [2,3]:
            self.advance();self.item.status=status
            result=self.sync()
            self.assertEqual(result['subscription']['billing_source'],'web')
        self.advance();self.item.status=1;self.tx.expiresDate=self.tx.purchaseDate+1
        self.assertEqual(self.sync()['apple_subscriptions'][0]['status'],'expired')

    def test_grace_requires_signed_unexpired_grace_end(self):
        self.item.status=4
        self.tx.expiresDate=self.tx.purchaseDate+1
        self.renewal.gracePeriodExpiresDate=self.tx.signedDate+86400000
        result=self.sync()
        self.assertEqual(result['apple_subscriptions'][0]['status'],'grace')
        self.assertIn('apple',result['subscription']['active_billing_sources'])
        self.advance();self.renewal.gracePeriodExpiresDate=self.tx.purchaseDate+2
        self.assertEqual(self.sync()['subscription']['active_billing_sources'],['web'])

    def test_renewal_preference_cancel_remains_active_until_expiry(self):
        self.renewal.autoRenewStatus=0
        result=self.sync()
        self.assertFalse(result['apple_subscriptions'][0]['auto_renews'])
        self.assertIn('apple',result['subscription']['active_billing_sources'])

    def test_renewal_updates_period_without_extra_subscription(self):
        self.sync();self.advance();self.tx.transactionId='10002'
        self.tx.expiresDate+=86400000
        self.sync()
        self.assertEqual(len(self.query('SELECT * FROM apple_transactions')),2)
        self.assertEqual(len(self.query("SELECT * FROM subscriptions WHERE provider='apple'")),1)

    def test_wrong_bundle_environment_and_ownership_type(self):
        for field,bad in [('bundleId','wrong'),('environment','Sandbox'),('inAppOwnershipType','FAMILY_SHARED')]:
            good=getattr(self.tx,field);setattr(self.tx,field,bad)
            with self.assertRaises(AppleBillingError): self.sync()
            setattr(self.tx,field,good)
        self.gateway.statuses.assert_not_called()

    def test_notification_duplicate_only_verified_once_per_delivery(self):
        self.assertEqual(self.service.notification('note')['outcome'],'reconciled')
        self.assertTrue(self.service.notification('note')['duplicate'])
        self.assertEqual(self.gateway.notification.call_count,2)
        self.gateway.statuses.assert_called_once()
        self.assertEqual(len(self.query('SELECT * FROM apple_notifications')),1)

    def test_notification_retry_after_apple_failure_preserves_stripe(self):
        self.gateway.statuses.side_effect=AppleBillingError('apple_unavailable')
        with self.assertRaises(AppleBillingError): self.service.notification('note')
        self.assertEqual(self.query('SELECT * FROM apple_notifications'),[])
        self.assertEqual(get_effective_entitlement(self.connect,1)['plan'],'paid')
        self.gateway.statuses.side_effect=None
        self.assertEqual(self.service.notification('note')['outcome'],'reconciled')

    def test_notification_before_sync_binds_only_known_signed_token(self):
        self.assertEqual(self.service.notification('note')['outcome'],'reconciled')
        self.assertEqual(self.query('SELECT user_id FROM apple_original_transactions')[0]['user_id'],1)

    def test_unbound_notification_acknowledged_without_grant(self):
        self.tx.appAccountToken=None
        self.assertEqual(self.service.notification('note')['outcome'],'unbound')
        self.assertEqual(self.query('SELECT * FROM apple_original_transactions'),[])

    def test_test_notification_does_not_call_status_api(self):
        self.note.notificationType='TEST'
        self.assertEqual(self.service.notification('note')['outcome'],'test')
        self.gateway.statuses.assert_not_called()

    def test_invalid_signed_payload_no_db_mutation(self):
        self.gateway.notification.side_effect=AppleBillingError('verification_failed')
        with self.assertRaises(AppleBillingError):self.service.notification('bad')
        self.assertEqual(self.query('SELECT * FROM apple_notifications'),[])

    def test_atomic_failure_rolls_back_ownership_notification_and_subscription(self):
        with patch.object(self.service,'_write_state',side_effect=RuntimeError('synthetic secret database path')):
            with self.assertRaises(AppleBillingError) as error:
                self.service.notification('note')
        self.assertEqual(error.exception.code,'storage_unavailable')
        for table in ['apple_notifications','apple_original_transactions','apple_transactions']:
            self.assertEqual(self.query('SELECT * FROM '+table),[])
        self.assertEqual(self.service.notification('note')['outcome'],'reconciled')

    def test_sandbox_cannot_grant_production_access(self):
        self.gateway.config.environment='Sandbox'
        self.gateway.statuses.return_value.environment='Sandbox'
        self.tx.environment='Sandbox';self.renewal.environment='Sandbox'
        self.tx.productId='nova.max.monthly'
        self.assertEqual(self.sync()['subscription']['billing_source'],'web')
        with patch.dict(os.environ,{'APPLE_ENVIRONMENT':'Sandbox'}):
            self.assertEqual(get_effective_entitlement(self.connect,1)['plan'],'max')

    def test_migration_idempotent(self):
        self.sync();before=self.query('SELECT * FROM subscriptions')
        migrate_apple_billing(self.fixture.db)
        self.assertEqual(before,self.query('SELECT * FROM subscriptions'))

    def test_concurrent_notification_retries_commit_once(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:self.service.notification('note'),range(4)))
        self.assertEqual(sum(not r.get('duplicate',False) for r in results),1)
        self.assertEqual(len(self.query('SELECT * FROM apple_notifications')),1)
        self.assertEqual(len(self.query('SELECT * FROM apple_original_transactions')),1)

    def test_out_of_order_notification_uses_current_state_not_old_event_type(self):
        self.tx.productId='nova.max.monthly';self.sync()
        self.note.notificationType='REFUND'
        self.note.signedDate-=86400000
        self.advance() # API current snapshot is still active after the old refund.
        self.service.notification('old-refund')
        self.assertEqual(get_effective_entitlement(self.connect,1)['plan'],'max')

    def test_wrong_notification_bundle_app_and_environment_rejected(self):
        for field,bad in [('bundleId','wrong'),('appAppleId',12),('environment','Sandbox')]:
            good=getattr(self.note.data,field);setattr(self.note.data,field,bad)
            with self.assertRaises(AppleBillingError):self.service.notification('bad')
            setattr(self.note.data,field,good)
        self.gateway.statuses.assert_not_called()

    def test_unknown_renewal_status_is_not_reported_as_true(self):
        self.renewal.autoRenewStatus=None
        self.assertIsNone(self.sync()['apple_subscriptions'][0]['auto_renews'])

    def test_postgres_migration_2_contract_and_skip(self):
        db=Mock();db.execute.return_value.fetchone.return_value=None
        migrate_apple_billing(db,postgres=True)
        statements=[c.args[0] for c in db.execute.call_args_list]
        self.assertEqual(statements[:2],["SET LOCAL lock_timeout = '5s'","SET LOCAL statement_timeout = '60s'"])
        self.assertIn('LOCK TABLE subscriptions IN ACCESS EXCLUSIVE MODE',statements)
        self.assertTrue(any('user_id INTEGER NOT NULL UNIQUE' in s for s in statements))
        self.assertFalse(any('DROP ' in s for s in statements))
        db.commit.assert_called_once();db.rollback.assert_not_called()
        db.reset_mock();db.execute.return_value.fetchone.side_effect=[{'name':'billing_migrations'},{'id':2}]
        migrate_apple_billing(db,postgres=True)
        self.assertEqual(db.execute.call_count,4)

    def test_account_token_idempotent_and_user_scoped(self):
        self.assertEqual(self.token,self.service.issue_account_token(1)['app_account_token'])
        self.assertNotEqual(self.token,self.service.issue_account_token(2)['app_account_token'])


class GatewayTests(unittest.TestCase):
    def test_missing_config_without_reading_real_environment(self):
        with patch.dict(os.environ,{},clear=True), patch('pathlib.Path.read_bytes') as read:
            with self.assertRaises(AppleBillingError) as error: AppleConfig.load()
            self.assertEqual(error.exception.code,'not_configured');read.assert_not_called()

    def test_production_configuration_defaults_and_unsupported_environment(self):
        env={'APPLE_KEY_ID':'synthetic','APPLE_ISSUER_ID':'synthetic',
             'APPLE_PRIVATE_KEY_PATH':'/synthetic/key','APPLE_ROOT_CA_PATHS':'/synthetic/root'}
        with patch.dict(os.environ,env,clear=True):
            cfg=AppleConfig.load()
            self.assertEqual(cfg.bundle_id,'com.amirnyv.Nova');self.assertEqual(cfg.app_id,6817116419)
            with patch.dict(os.environ,{'APPLE_ENVIRONMENT':'Xcode'}):
                with self.assertRaises(AppleBillingError): AppleConfig.load()

    def test_official_sdk_wiring_with_synthetic_key_and_roots(self):
        import sys
        from types import ModuleType
        modules={name:ModuleType(name) for name in [
            'appstoreserverlibrary','appstoreserverlibrary.api_client',
            'appstoreserverlibrary.models','appstoreserverlibrary.models.Environment',
            'appstoreserverlibrary.signed_data_verifier']}
        client=Mock();verifier=Mock()
        modules['appstoreserverlibrary.api_client'].AppStoreServerAPIClient=client
        modules['appstoreserverlibrary.models.Environment'].Environment=lambda v:v
        modules['appstoreserverlibrary.signed_data_verifier'].SignedDataVerifier=verifier
        cfg=AppleConfig('Production','com.amirnyv.Nova',6817116419,'fake-key-id','fake-issuer','/fake/key',('/fake/root',))
        with patch.dict(sys.modules,modules), patch('pathlib.Path.read_bytes',side_effect=[b'fake-root',b'fake-key']):
            gateway=AppleGateway(cfg)
        verifier.assert_called_once_with([b'fake-root'],True,'Production','com.amirnyv.Nova',6817116419)
        client.assert_called_once_with(b'fake-key','fake-key-id','fake-issuer','com.amirnyv.Nova','Production')
        gateway.transaction('signed');verifier.return_value.verify_and_decode_signed_transaction.assert_called_once_with('signed')
        gateway.renewal('renewal');verifier.return_value.verify_and_decode_renewal_info.assert_called_once_with('renewal')
        gateway.notification('note');verifier.return_value.verify_and_decode_notification.assert_called_once_with('note')
        gateway.statuses('100');client.return_value.get_all_subscription_statuses.assert_called_once_with('100')

    def test_official_verifier_exception_sanitized_and_retryable(self):
        gateway=AppleGateway.__new__(AppleGateway)
        gateway.verifier=Mock()
        for status,expected in [('VERIFICATION_FAILURE','verification_failed'),('RETRYABLE_VERIFICATION_FAILURE','apple_unavailable')]:
            failure=RuntimeError('SYNTHETIC_PRIVATE_PAYLOAD')
            failure.status=Obj(name=status)
            gateway.verifier.verify_and_decode_signed_transaction.side_effect=failure
            with self.assertRaises(AppleBillingError) as error:gateway.transaction('fake-jws')
            self.assertEqual(error.exception.code,expected)
            self.assertNotIn('SYNTHETIC',str(error.exception))


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.app=Flask('apple_routes_test');self.app.secret_key='synthetic-test-key'
        manager=LoginManager(self.app)
        class User(UserMixin):
            id='17'
        manager.user_loader(lambda uid:User())
        tree=ast.parse((Path(__file__).resolve().parents[1]/'app.py').read_text())
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='protect_browser_mutations')
        ns=dict(app=self.app,request=request,session=session,jsonify=jsonify,hmac=hmac)
        exec(compile(ast.Module(body=[node],type_ignores=[]),'isolated_csrf','exec'),ns)
        register_apple_billing(self.app,Mock())
        self.client=self.app.test_client()
        with self.client.session_transaction() as state:
            state['_user_id']='17';state['_fresh']=True;state['csrf_token']='synthetic-csrf'
        patcher=patch('services.apple_routes.AppleBilling')
        self.service=patcher.start().return_value;self.addCleanup(patcher.stop)
        self.service.sync.return_value={'ok':True,'subscription':{'plan':'max','billing_source':'apple'}}
        self.service.notification.return_value={'ok':True}
        self.service.issue_account_token.return_value={'ok':True,'app_account_token':str(uuid4())}

    def test_authenticated_sync_contract_and_server_identity(self):
        response=self.client.post('/api/billing/apple/sync',json={'signed_transaction':'jws'},headers={'X-CSRF-Token':'synthetic-csrf'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['subscription']['plan'],'max')
        self.service.sync.assert_called_once_with(17,'jws')

    def test_login_and_csrf_required_for_sync_and_token(self):
        for path in ['sync','account-token']:
            response=self.client.post('/api/billing/apple/'+path,json={})
            self.assertEqual(response.status_code,403)
            anon=self.app.test_client()
            with anon.session_transaction() as state:state['csrf_token']='synthetic-csrf'
            response=anon.post('/api/billing/apple/'+path,json={},headers={'X-CSRF-Token':'synthetic-csrf'})
            self.assertEqual(response.status_code,401)
        self.service.sync.assert_not_called();self.service.issue_account_token.assert_not_called()

    def test_notification_has_no_login_or_csrf_requirement(self):
        response=self.app.test_client().post('/api/billing/apple/notifications',json={'signedPayload':'jws'})
        self.assertEqual(response.status_code,200)
        self.service.notification.assert_called_once_with('jws')

    def test_client_authority_and_large_payload_rejected(self):
        for body in [{'signed_transaction':'jws','plan':'max'},{'signed_transaction':'jws','user_id':2},
                     {'status':'active'}, [], {'signed_transaction':'x'*70001}]:
            result=self.client.post('/api/billing/apple/sync',json=body,headers={'X-CSRF-Token':'synthetic-csrf'})
            self.assertEqual(result.status_code,400)
        self.service.sync.assert_not_called()

    def test_route_to_reconciliation_with_only_gateway_mocked(self):
        fixture=AppleTests();fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        # Use the route fixture's authenticated user ID, never request authority.
        fixture.fixture.db.execute('INSERT INTO users(id) VALUES(17)')
        fixture.fixture.db.commit()
        fixture.tx.appAccountToken=fixture.service.issue_account_token(17)['app_account_token']
        fixture.tx.productId='nova.max.monthly'
        with patch('services.apple_routes.AppleBilling',return_value=fixture.service):
            result=self.client.post('/api/billing/apple/sync',json={'signed_transaction':'jws'},
                                    headers={'X-CSRF-Token':'synthetic-csrf'})
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.json['subscription']['plan'],'max')
        self.assertEqual(result.headers['Cache-Control'],'no-store')
        self.assertEqual(fixture.query('SELECT user_id FROM apple_original_transactions')[0]['user_id'],17)

    def test_safe_error_and_log_contract(self):
        self.service.sync.side_effect=RuntimeError('SYNTHETIC_SECRET')
        with self.assertLogs('services.apple_routes',level='ERROR') as logs:
            result=self.client.post('/api/billing/apple/sync',json={'signed_transaction':'jws'},headers={'X-CSRF-Token':'synthetic-csrf'})
        self.assertEqual(result.status_code,503)
        self.assertNotIn('SYNTHETIC_SECRET',result.text+str(logs.output))


if __name__=='__main__': unittest.main()

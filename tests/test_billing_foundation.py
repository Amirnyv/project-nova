"""Billing migrations and entitlement tests; isolated SQLite, no app imports/API calls."""
import ast
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock

from flask import Flask, jsonify, request
from types import SimpleNamespace
from services.billing_schema import migrate_billing
from services.billing_entitlements import (
    effective_entitlement, get_effective_entitlement, get_stripe_subscription, save_provider_subscription,
)

ROOT = Path(__file__).resolve().parents[1]
APP = ast.parse((ROOT / 'app.py').read_text())


def app_functions(names, namespace):
    nodes = [node for node in APP.body if isinstance(node, ast.FunctionDef) and node.name in names]
    for node in nodes:
        node.decorator_list = []
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'billing_app_functions', 'exec'), namespace)
    return namespace


class BillingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'billing.sqlite'
        self.db = self.connect()
        self.addCleanup(self.db.close)
        self.db.executescript('''CREATE TABLE users (id INTEGER PRIMARY KEY);
            INSERT INTO users VALUES (1),(2);
            CREATE TABLE subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL UNIQUE,
                plan TEXT NOT NULL DEFAULT 'none', status TEXT NOT NULL DEFAULT 'inactive',
                provider TEXT DEFAULT '', provider_customer_id TEXT DEFAULT '',
                provider_subscription_id TEXT DEFAULT '', current_period_start TIMESTAMP,
                current_period_end TIMESTAMP, cancel_at_period_end INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id));
            INSERT INTO subscriptions(user_id,plan,status,provider,provider_customer_id,provider_subscription_id)
                VALUES(1,'paid','active','','cus_test','sub_test');
            CREATE TABLE ai_usage (user_id INTEGER, total_tokens INTEGER, created_at TIMESTAMP);
        ''')

    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    def migrate(self):
        migrate_billing(self.db)

    def save(self, provider='stripe', sub='sub_test', plan='pro', status='active', user=1):
        save_provider_subscription(self.connect, user, plan, status, provider, 'cus_test' if provider == 'stripe' else '', sub)

    def apple_verified_fixture(self, plan='max'):
        # Test-only verified entitlement, NOT a live transaction or verification API.
        self.save('apple', 'original_test', plan, 'inactive')
        self.db.execute("""UPDATE subscriptions SET status='active', verified_at=CURRENT_TIMESTAMP,
            current_period_start=?, current_period_end=? WHERE provider='apple'""",
            ((datetime.now(timezone.utc) - timedelta(days=1)).isoformat(), (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()))
        self.db.commit()

    def test_migration_preserves_rows_ids_dates_and_repeats(self):
        before = dict(self.db.execute('SELECT * FROM subscriptions').fetchone())
        self.migrate()
        self.migrate()
        after = dict(self.db.execute('SELECT * FROM subscriptions').fetchone())
        self.assertEqual({k:v for k,v in after.items() if k not in {'provider','verified_at'}},
                         {k:v for k,v in before.items() if k != 'provider'})
        self.assertEqual(after['provider'], 'stripe')
        self.assertEqual(get_effective_entitlement(self.connect,1)['plan'], 'paid')

    def test_stripe_apple_coexist_highest_tier_and_no_combined_quota(self):
        self.migrate()
        self.apple_verified_fixture()
        effective = get_effective_entitlement(self.connect,1)
        self.assertEqual(effective['plan'], 'max')
        self.assertEqual(effective['billing_source'], 'apple')
        self.assertEqual(effective['active_billing_sources'], ['apple','web'])
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM subscriptions').fetchone()[0], 2)
        ns = app_functions({'check_ai_usage_limit'}, {
            'get_active_subscription': lambda uid: get_effective_entitlement(self.connect,uid),
            'PLAN_TOKEN_LIMITS': {'developer':None,'paid':600000,'pro':600000,'max':1500000},
            'get_current_period_usage': lambda *args:100})
        self.assertEqual(ns['check_ai_usage_limit'](1)['remaining'],1499900)

    def test_equal_tier_prefers_web_developer_beats_max(self):
        self.migrate()
        self.save(plan='max')
        self.apple_verified_fixture()
        self.assertEqual(get_effective_entitlement(self.connect,1)['billing_source'],'web')
        self.save(plan='developer')
        self.assertEqual(get_effective_entitlement(self.connect,1)['plan'],'developer')

    def test_apple_placeholder_and_expired_do_not_grant_or_overwrite(self):
        self.migrate()
        self.save('apple','original_test','max','inactive')
        self.assertEqual(get_effective_entitlement(self.connect,1)['plan'],'paid')
        with self.assertRaises(ValueError):
            self.save('apple','original_test','max','active')
        self.apple_verified_fixture()
        self.db.execute("UPDATE subscriptions SET current_period_end='2000-01-01' WHERE provider='apple'")
        self.db.commit()
        self.assertEqual(get_effective_entitlement(self.connect,1)['plan'],'paid')

    def test_upsert_idempotent_and_cannot_transfer_ownership(self):
        self.migrate()
        self.save(); self.save(plan='max')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM subscriptions').fetchone()[0],1)
        with self.assertRaises(ValueError):
            self.save(user=2)
        self.assertEqual(get_effective_entitlement(self.connect,1)['plan'],'max')
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO subscriptions(user_id,provider,provider_subscription_id) VALUES(2,'stripe','sub_test')")
        self.db.rollback()
        self.save('apple','sub_test','pro','inactive')

    def test_duplicate_migration_aborts_without_data_loss(self):
        self.db.execute("INSERT INTO subscriptions(user_id,plan,status,provider,provider_subscription_id) VALUES(2,'max','active','stripe','sub_test')")
        self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.migrate()
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM subscriptions').fetchone()[0],2)
        self.assertNotIn('verified_at',[r['name'] for r in self.db.execute('PRAGMA table_info(subscriptions)')])

    def test_original_ownership_and_notification_deduplication(self):
        self.migrate()
        self.db.execute("INSERT INTO apple_original_transactions(original_transaction_id,user_id) VALUES('original',1)")
        self.db.execute("INSERT INTO apple_transactions(user_id,transaction_id,original_transaction_id,product_id,plan) VALUES(1,'tx','original','nova.pro.monthly','pro')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO apple_transactions(user_id,transaction_id,original_transaction_id,product_id,plan) VALUES(2,'tx2','original','nova.pro.monthly','pro')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE apple_original_transactions SET user_id=2")
        self.db.execute('UPDATE apple_original_transactions SET last_signed_at=CURRENT_TIMESTAMP')
        self.db.execute("INSERT INTO apple_notifications(notification_uuid,signed_at,notification_type) VALUES('n1',CURRENT_TIMESTAMP,'TEST')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO apple_notifications(notification_uuid,signed_at,notification_type) VALUES('n1',CURRENT_TIMESTAMP,'TEST')")

    def test_portal_reads_stripe_even_when_apple_wins(self):
        self.migrate(); self.apple_verified_fixture()
        self.assertEqual(get_stripe_subscription(self.connect,1)['provider'],'stripe')
        stripe = Mock()
        stripe.billing_portal.Session.create.return_value = SimpleNamespace(url='https://example.invalid/portal')
        app = Flask('billing')
        ns = app_functions({'create_portal_session'}, dict(get_stripe_subscription=get_stripe_subscription,
            get_db=self.connect,current_user=SimpleNamespace(id=1),jsonify=jsonify,request=request,stripe=stripe))
        with app.test_request_context('/'):
            response = ns['create_portal_session']()
            self.assertEqual(response.json['url'],'https://example.invalid/portal')
        self.assertEqual(stripe.billing_portal.Session.create.call_args.kwargs['customer'],'cus_test')

    def test_every_webhook_subscription_update_is_provider_scoped(self):
        self.migrate()
        self.save('apple','sub_test','max','inactive')
        webhook = next(n for n in APP.body if isinstance(n,ast.FunctionDef) and n.name=='stripe_webhook')
        queries = [n.value for n in ast.walk(webhook) if isinstance(n,ast.Constant) and isinstance(n.value,str)
                   and 'UPDATE subscriptions' in n.value]
        self.assertEqual(len(queries),4)
        for sql in queries:
            self.assertIn("provider = 'stripe'",sql)
            count = sql.count('?')
            params = {6: ('max','active',None,None,0,'sub_test'),
                      1: ('sub_test',), 4: ('active',None,None,'sub_test')}[count]
            self.db.execute(sql,params)
        self.assertEqual(self.db.execute("SELECT status FROM subscriptions WHERE provider='apple'").fetchone()[0],'inactive')

    def test_existing_apple_transactions_backfill_preserves_data(self):
        self.db.executescript("""CREATE TABLE apple_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
            transaction_id TEXT NOT NULL UNIQUE, original_transaction_id TEXT NOT NULL,
            product_id TEXT NOT NULL, plan TEXT NOT NULL, status TEXT DEFAULT 'active',
            purchased_at TIMESTAMP, expires_at TIMESTAMP, revoked_at TIMESTAMP,
            environment TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            INSERT INTO apple_transactions(user_id,transaction_id,original_transaction_id,product_id,plan)
                VALUES(1,'old_tx','old_original','nova.pro.monthly','pro');""")
        before = dict(self.db.execute('SELECT * FROM apple_transactions').fetchone())
        self.migrate()
        after = dict(self.db.execute('SELECT * FROM apple_transactions').fetchone())
        self.assertEqual(before, {k:v for k,v in after.items() if k != 'signed_at'})
        owner = self.db.execute('SELECT user_id FROM apple_original_transactions').fetchone()
        self.assertEqual(owner['user_id'],1)

    def test_autoincrement_high_water_mark_preserved(self):
        self.db.execute("INSERT INTO subscriptions(id,user_id) VALUES(99,2)")
        self.db.execute('DELETE FROM subscriptions WHERE id=99')
        self.db.commit()
        self.migrate()
        self.save('apple','new_original','pro','inactive')
        self.assertGreater(self.db.execute("SELECT id FROM subscriptions WHERE provider='apple'").fetchone()[0],99)

    def test_postgres_migration_contract_and_repeat(self):
        db = Mock()
        db.execute.return_value.fetchone.return_value = None
        db.execute.return_value.fetchall.return_value = [
            {'conname':'subscriptions_user_id_key','definition':'UNIQUE (user_id)'}]
        migrate_billing(db, postgres=True)
        statements = [c.args[0] for c in db.execute.call_args_list]
        self.assertEqual(statements[:2], ["SET LOCAL lock_timeout = '5s'", "SET LOCAL statement_timeout = '60s'"])
        self.assertIn('LOCK TABLE subscriptions IN ACCESS EXCLUSIVE MODE', statements)
        self.assertIn('ALTER TABLE subscriptions DROP CONSTRAINT "subscriptions_user_id_key"',statements)
        self.assertTrue(any('FOREIGN KEY(original_transaction_id, user_id)' in sql for sql in statements))
        self.assertFalse(any('DROP TABLE' in sql for sql in statements))
        db.commit.assert_called_once()
        db.rollback.assert_not_called()
        db.reset_mock()
        db.execute.return_value.fetchone.side_effect=[{'name':'billing_migrations'},{'id':1}]
        migrate_billing(db,postgres=True)
        self.assertEqual(db.execute.call_count,4)

    def test_future_apple_client_routes_require_csrf(self):
        import hmac
        from flask import session
        app=Flask('csrf_billing')
        app.secret_key='synthetic-test-key'
        ns=app_functions({'protect_browser_mutations'},dict(request=request,session=session,
                                                           jsonify=jsonify,hmac=hmac))
        app.before_request(ns['protect_browser_mutations'])
        app.add_url_rule('/api/billing/apple/sync','apple_sync',lambda: 'ok',methods=['POST'])
        app.add_url_rule('/api/billing/apple/notifications','apple_notification',lambda: 'ok',methods=['POST'])
        client=app.test_client()
        self.assertEqual(client.post('/api/billing/apple/sync',json={}).status_code,403)
        with client.session_transaction() as state:
            state['csrf_token']='synthetic-csrf'
        self.assertEqual(client.post('/api/billing/apple/sync',json={},headers={'X-CSRF-Token':'synthetic-csrf'}).status_code,200)
        self.assertEqual(client.post('/api/billing/apple/notifications',json={}).status_code,200)

    def test_usage_reports_effective_sources(self):
        self.migrate(); self.apple_verified_fixture()
        app=Flask('usage')
        ns=app_functions({'ai_usage'},dict(current_user=SimpleNamespace(id=1),jsonify=jsonify,
            get_active_subscription=lambda uid:get_effective_entitlement(self.connect,uid),
            check_ai_usage_limit=lambda uid:{'used':10,'limit':1500000,'remaining':1499990},
            PLAN_TOKEN_LIMITS={'max':1500000},get_user_usage_total=lambda uid:10))
        with app.app_context():
            result=ns['ai_usage']().json
        self.assertEqual(result['subscription']['billing_source'],'apple')
        self.assertEqual(result['subscription']['active_billing_sources'],['apple','web'])


if __name__=='__main__':
    unittest.main()

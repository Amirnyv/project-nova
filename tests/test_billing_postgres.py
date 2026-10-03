"""Opt-in real PostgreSQL tests; always creates its OWN disposable local cluster.

Run from repository root:
  venv/bin/python -B tests/test_billing_postgres.py --postgres-bin /path/to/bin
No dotenv/database/app import, production DSN, remote server, or backup is used.
Ordinary discovery skips these tests. Cluster listens on a private Unix socket only.
"""
import argparse
import ast
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.billing_schema import migrate_billing
from services.apple_schema import migrate_apple_billing

PG_BIN = None
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--postgres-bin', required=True)
    parser.add_argument('--local-worker', action='store_true', help=argparse.SUPPRESS)
    args, rest = parser.parse_known_args()
    if not args.local_worker:
        # Do not let libpq consult any inherited PG* / DATABASE_URL / service
        # settings. The child receives no production credentials or environment.
        command = [sys.executable, '-B', str(Path(__file__).resolve()), '--local-worker',
                   '--postgres-bin', str(Path(args.postgres_bin).resolve()), *rest]
        result = subprocess.run(command, env={'PATH':'/usr/bin:/bin', 'LC_ALL':'C'})
        raise SystemExit(result.returncode)
    PG_BIN = Path(args.postgres_bin).resolve()
    sys.argv = [sys.argv[0]] + rest


@unittest.skipUnless(PG_BIN, 'Opt-in disposable PostgreSQL test; no external DSN accepted')
class PostgresMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        from psycopg.rows import dict_row
        cls.psycopg = psycopg
        cls.temp = tempfile.TemporaryDirectory(prefix='nova_pg_', dir='/private/tmp')
        cls.base = Path(cls.temp.name)
        cls.data = cls.base / 'data'
        cls.sock = cls.base / 'socket'
        cls.sock.mkdir(mode=0o700)
        cls.env = {'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'}
        cls.started = False
        cls.addClassCleanup(cls.cleanup_cluster)
        subprocess.run([str(PG_BIN/'initdb'), '-D', str(cls.data), '-U', 'nova_test', '-A', 'trust',
                        '--no-locale', '--encoding=UTF8'], env=cls.env, check=True, capture_output=True)
        subprocess.run([str(PG_BIN/'pg_ctl'), '-D', str(cls.data), '-l', str(cls.base/'server.log'),
                        '-o', f"-F -k {cls.sock} -h '' -p 55439", '-w', 'start'],
                       env=cls.env, check=True, capture_output=True)
        cls.started = True
        cls.params = dict(host=str(cls.sock), port=55439, user='nova_test', password='synthetic-unused', passfile='/dev/null', dbname='postgres', sslmode='disable')
        with psycopg.connect(**cls.params) as db:
            print('Local PostgreSQL:', db.execute('SELECT version()').fetchone()[0])
            assert db.execute('SHOW listen_addresses').fetchone()[0] == ''
        # Compile the real wrapper/startup functions without executing top-level
        # environment reads, database config, .env loading, or Flask startup.
        tree = ast.parse((ROOT/'database.py').read_text())
        names = {'DatabaseCursor','PostgresConnection','get_db','init_postgres_db','init_db'}
        cls.nodes = [n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in names]
        cls.dict_row = staticmethod(dict_row)

    @classmethod
    def cleanup_cluster(cls):
        if cls.started:
            subprocess.run([str(PG_BIN/'pg_ctl'), '-D', str(cls.data), '-m','fast','-w','stop'],
                           env=cls.env, check=True, capture_output=True)
        cls.temp.cleanup()

    def setUp(self):
        self.schema = 'case_' + uuid4().hex
        with self.psycopg.connect(**self.params, autocommit=True) as db:
            db.execute('CREATE SCHEMA ' + self.schema)
        params = dict(self.params, options=f'-c search_path={self.schema}')
        ns = dict(psycopg=self.psycopg, dict_row=self.dict_row, re=re, sqlite3=sqlite3,
                  USE_POSTGRES=True, DATABASE_URL=self.psycopg.conninfo.make_conninfo(**params))
        exec(compile(ast.Module(body=self.nodes,type_ignores=[]),'isolated_database','exec'),ns)
        self.ns = ns
        self.ns['init_postgres_db']()  # Actual pre-migration PostgreSQL schema.
        self.db = self.ns['get_db']()
        self.addCleanup(self.db.close)
        for uid, plan, status in [(1,'pro','active'),(2,'max','active'),(3,'paid','canceled'),(4,'pro','inactive')]:
            self.db.execute('INSERT INTO users(id,username,email,password_hash) VALUES(?,?,?,?)',
                            (uid,f'user{uid}',f'user{uid}@example.invalid','synthetic'))
            self.db.execute('''INSERT INTO subscriptions(id,user_id,plan,status,provider,
                provider_customer_id,provider_subscription_id,current_period_start,current_period_end,
                cancel_at_period_end,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                (uid,uid,plan,status,'stripe' if uid!=1 else '',f'cus_synthetic{uid}',f'sub_synthetic{uid}',
                 '2026-09-01','2026-10-01',int(uid==3),'2026-01-01','2026-09-01'))
        # Representative logical restore should preserve/set sequence positions.
        self.db.execute("SELECT setval(pg_get_serial_sequence('subscriptions','id'), 40)")
        self.db.commit()

    def rows(self):
        return self.db.execute('SELECT * FROM subscriptions ORDER BY id').fetchall()

    def migrate(self):
        migrate_billing(self.db,postgres=True)
        migrate_apple_billing(self.db,postgres=True)

    def test_legacy_rows_ids_and_sequence_preserved_and_restart(self):
        before = self.rows();self.db.commit()
        self.migrate()
        after = self.rows()
        for old,new in zip(before,after):
            for key,val in old.items():
                self.assertEqual(new[key], 'stripe' if key=='provider' and val=='' else val)
        self.assertEqual(len(after),4)
        self.db.commit()
        self.ns['init_db']() # real startup path on already-migrated DB
        self.assertEqual(after,self.rows())
        inserted=self.db.execute("""INSERT INTO subscriptions(user_id,plan,status,provider,provider_subscription_id)
            VALUES(1,'max','inactive','apple','synthetic_original')""")
        self.assertEqual(inserted.lastrowid,41)
        self.db.commit()

    def test_constraints_indexes_provider_isolation_and_apple_ownership(self):
        self.migrate()
        indexes=self.db.execute("SELECT indexname FROM pg_indexes WHERE schemaname=current_schema()").fetchall()
        names={row['indexname'] for row in indexes}
        self.assertTrue({'subscriptions_provider_identity','subscriptions_provider_legacy_user',
            'idx_apple_transactions_user_id','idx_apple_transactions_original_transaction_id'} <= names)
        self.assertNotIn('subscriptions_user_id_key',names)
        self.db.execute("INSERT INTO subscriptions(user_id,provider,provider_subscription_id) VALUES(1,'apple','sub_synthetic1')")
        self.db.execute("INSERT INTO subscriptions(user_id,provider,provider_subscription_id) VALUES(1,'legacy','')")
        self.db.execute("INSERT INTO apple_account_tokens(user_id,app_account_token) VALUES(1,'synthetic-token')")
        self.db.execute("INSERT INTO apple_original_transactions(original_transaction_id,user_id) VALUES('original',1)")
        self.db.execute("""INSERT INTO apple_transactions(user_id,transaction_id,original_transaction_id,product_id,plan)
            VALUES(1,'tx','original','nova.pro.monthly','pro')""")
        self.db.commit()
        for sql in [
            "INSERT INTO subscriptions(user_id,provider,provider_subscription_id) VALUES(1,'legacy',NULL)",
            "INSERT INTO subscriptions(user_id,provider,provider_subscription_id) VALUES(2,'stripe','sub_synthetic1')",
            "INSERT INTO apple_account_tokens(user_id,app_account_token) VALUES(2,'synthetic-token')",
            "INSERT INTO apple_original_transactions(original_transaction_id,user_id) VALUES('original',2)",
            "INSERT INTO apple_transactions(user_id,transaction_id,original_transaction_id,product_id,plan) VALUES(2,'tx2','original','nova.pro.monthly','pro')",
        ]:
            with self.assertRaises(sqlite3.IntegrityError): self.db.execute(sql)
            self.db.rollback()
        with self.assertRaises(self.psycopg.errors.RaiseException):
            self.db.execute('UPDATE apple_original_transactions SET user_id=2')
        self.db.rollback()
        self.db.execute('UPDATE apple_original_transactions SET last_signed_at=CURRENT_TIMESTAMP')
        self.db.commit()

    def test_duplicate_legacy_identifiers_rollback_and_recover(self):
        self.db.execute("UPDATE subscriptions SET provider_subscription_id='sub_synthetic1' WHERE user_id=2")
        self.db.commit();before=self.rows();self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):migrate_billing(self.db,postgres=True)
        self.assertEqual(before,self.rows())
        self.assertIsNone(self.db.execute("SELECT to_regclass('billing_migrations') AS name").fetchone()['name'])
        self.db.execute("UPDATE subscriptions SET provider_subscription_id='sub_synthetic2' WHERE user_id=2")
        self.db.commit();self.migrate()
        self.assertEqual(len(self.rows()),4)

    def test_mid_migration1_failure_rolls_back_all_ddl(self):
        before=self.rows();self.db.commit()
        class Fail:
            def execute(_,sql,parameters=()):
                if 'CREATE FUNCTION nova_apple_owner_immutable' in sql:raise RuntimeError('Injected migration failure')
                return self.db.execute(sql,parameters)
            def rollback(_):self.db.rollback()
            def commit(_):self.db.commit()
        with self.assertRaises(RuntimeError):migrate_billing(Fail(),postgres=True)
        self.assertEqual(before,self.rows())
        self.assertIsNone(self.db.execute("SELECT to_regclass('apple_transactions') AS name").fetchone()['name'])
        self.db.commit();self.migrate()

    def test_mid_migration2_failure_leaves_valid_v1_then_recovers(self):
        migrate_billing(self.db,postgres=True)
        before=self.rows();self.db.commit()
        class Fail:
            def execute(_,sql,parameters=()):
                if 'ADD COLUMN apple_state' in sql:raise RuntimeError('Injected migration failure')
                return self.db.execute(sql,parameters)
            def rollback(_):self.db.rollback()
            def commit(_):self.db.commit()
        with self.assertRaises(RuntimeError):migrate_apple_billing(Fail(),postgres=True)
        self.assertEqual(before,self.rows())
        self.assertIsNone(self.db.execute("SELECT to_regclass('apple_account_tokens') AS name").fetchone()['name'])
        self.assertEqual(self.db.execute('SELECT id FROM billing_migrations').fetchall(),[{'id':1}])
        self.db.commit();self.ns['init_db']()
        self.assertEqual(self.db.execute('SELECT id FROM billing_migrations ORDER BY id').fetchall(),[{'id':1},{'id':2}])

    def test_concurrent_migration_workers(self):
        def run():
            db=self.ns['get_db']()
            try:
                migrate_billing(db,postgres=True);migrate_apple_billing(db,postgres=True)
            finally:db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(run) for _ in range(2)]
            for future in futures:future.result(timeout=20)
        self.assertEqual(len(self.rows()),4)
        self.assertEqual(self.db.execute('SELECT COUNT(*) AS n FROM billing_migrations').fetchone()['n'],2)

    def test_reader_blocks_ddl_and_timeout_rolls_back(self):
        # A real reader blocks DDL; the migration's own timeout must release it.
        blocker=self.ns['get_db']();self.addCleanup(blocker.close)
        blocker.execute('SELECT * FROM subscriptions') # AccessShare until rollback
        started=time.monotonic()
        with self.assertRaises(sqlite3.OperationalError):
            migrate_billing(self.db,postgres=True)
        self.assertLess(time.monotonic()-started,8)
        blocker.rollback()
        self.assertEqual(len(self.rows()),4)
        self.db.commit();self.migrate()

    def test_completed_startup_does_not_request_exclusive_subscription_lock(self):
        self.migrate()
        blocker=self.ns['get_db']();self.addCleanup(blocker.close)
        blocker.execute('SELECT * FROM subscriptions')
        started=time.monotonic()
        self.ns['init_db']()
        self.assertLess(time.monotonic()-started,2)
        blocker.rollback()

    def test_existing_marker_rerun_and_apple_columns(self):
        self.migrate();self.migrate()
        self.assertEqual(self.db.execute("SHOW lock_timeout").fetchone()["lock_timeout"], "0")
        self.assertEqual(self.db.execute("SHOW statement_timeout").fetchone()["statement_timeout"], "0")
        columns={r['column_name'] for r in self.db.execute("""SELECT column_name FROM information_schema.columns
            WHERE table_schema=current_schema() AND table_name='subscriptions'""").fetchall()}
        self.assertTrue({'verified_at','apple_environment','apple_state','apple_renewal_at','apple_auto_renews'} <= columns)
        self.db.execute("INSERT INTO apple_notifications(notification_uuid,signed_at,notification_type) VALUES('n1',CURRENT_TIMESTAMP,'TEST')")
        self.db.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO apple_notifications(notification_uuid,signed_at,notification_type) VALUES('n1',CURRENT_TIMESTAMP,'TEST')")
        self.db.rollback()


    def test_paper_postgres_atomic_duplicates_and_chat_account(self):
        from services.paper_trading import PaperTrading, PaperError
        from services.paper_schema import initialize_paper_schema
        from unittest.mock import patch
        self.ns['init_db']()
        self.ns['init_db']()
        now=1790951400.0
        service=PaperTrading(self.ns['get_db'],True,
            quote=lambda symbol:dict(symbol=symbol,close='100',timestamp=now,is_market_open=True,previous_close='90'),
            clock=lambda:now)
        preview=service.preview(1,dict(symbol='AAPL',side='BUY',unit='shares',amount='0.123456'))
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:service.execute(1,preview['preview_id']),range(4)))
        self.assertTrue(all(r==results[0] for r in results))
        self.assertEqual(len(service.transactions(1)['transactions']),1)
        self.assertEqual(service.portfolio(1)['holdings'][0]['shares'],'0.123456')
        with self.assertRaises(PaperError):service.execute(2,preview['preview_id'])
        # Legacy chat writer must use the same account and lock discipline.
        from agents import portfolio_agent
        with patch.object(portfolio_agent,'get_db',self.ns['get_db']),patch('database.USE_POSTGRES',True):
            self.assertTrue(portfolio_agent.buy_stock(1,'AAPL',1,100)['success'])
        self.assertEqual(service.portfolio(1)['holdings'][0]['shares'],'1.123456')
        initialize_paper_schema(self.ns['get_db'],True)
        self.assertEqual(len(service.transactions(1)['transactions']),2)
        service.reset(1)
        self.assertEqual(service.execute(1,preview['preview_id']),results[0])
        self.assertEqual(service.transactions(1)['transactions'],[])

    def test_paper_postgres_rollback_leaves_cash_and_preview_intact(self):
        from services.paper_trading import PaperTrading
        self.ns['init_db']()
        now=1790951400.0
        quote=lambda symbol:dict(symbol=symbol,close='100',timestamp=now,is_market_open=True)
        good=PaperTrading(self.ns['get_db'],True,quote=quote,clock=lambda:now)
        preview=good.preview(1,dict(symbol='AAPL',side='BUY',unit='shares',amount='1'))
        factory=self.ns['get_db']
        class Fail:
            def __init__(self):self.db=factory()
            def execute(self,sql,params=()):
                if 'INSERT INTO paper_trade_details' in sql:raise RuntimeError('Injected failure')
                return self.db.execute(sql,params)
            def commit(self):self.db.commit()
            def rollback(self):self.db.rollback()
            def close(self):self.db.close()
        broken=PaperTrading(Fail,True,quote=quote,clock=lambda:now)
        with self.assertRaises(RuntimeError):broken.execute(1,preview['preview_id'])
        self.assertEqual(good.portfolio(1)['cash'],'10000.00')
        self.assertEqual(good.transactions(1)['transactions'],[])
        good.execute(1,preview['preview_id'])
        self.assertEqual(len(good.transactions(1)['transactions']),1)


if __name__=='__main__':unittest.main(verbosity=2)

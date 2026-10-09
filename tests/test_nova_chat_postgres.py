"""Real PostgreSQL contract/race tests in an owned disposable local cluster only."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_billing_postgres as harness
from test_nova_chat import MessagingContract
from services.nova_chat_schema import migrate_nova_chat
from services.nova_profile_schema import migrate_nova_profiles


@unittest.skipUnless(harness.PG_BIN,'Opt-in disposable local PostgreSQL only')
class PostgreSQLMessagingTests(MessagingContract,harness.PostgresMigrationTests):
    postgres=True

    def setUp(self):
        super().setUp()
        self.connect=self.ns['get_db']
        migrate_nova_profiles(self.db,True)
        self.prepare()

    def test_concurrent_migration_and_startup(self):
        # Use a fresh schema so concurrency tests initial DDL, not just marker reads.
        fresh='fresh_'+self.schema
        self.db.execute('CREATE SCHEMA '+fresh);self.db.commit()
        def connect():
            db=self.connect()
            db.execute('SET search_path TO '+fresh)
            return db
        db=connect();db.execute('CREATE TABLE users(id INTEGER PRIMARY KEY)');db.commit()
        migrate_nova_profiles(db,True);db.close()
        def migrate(_):
            db=connect()
            try:migrate_nova_chat(db,True)
            finally:db.close()
        with ThreadPoolExecutor(3) as executor:list(executor.map(migrate,range(3)))
        db=connect()
        self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM nova_social_migrations').fetchone()['n'],2)
        db.close()
        self.ns['init_db']();self.ns['init_db']()

    def test_failed_migration_rollback(self):
        fresh='failure_'+self.schema
        self.db.execute('CREATE SCHEMA '+fresh)
        self.db.execute('SET search_path TO '+fresh)
        self.db.execute('CREATE TABLE users(id INTEGER PRIMARY KEY)');self.db.commit()
        migrate_nova_profiles(self.db,True)
        self.db.execute('CREATE TABLE nova_chat_blocks(id INTEGER PRIMARY KEY)');self.db.commit()
        with self.assertRaises(Exception):migrate_nova_chat(self.db,True)
        self.assertIsNone(self.db.execute("SELECT to_regclass('nova_chat_messages') AS name").fetchone()['name'])
        self.assertEqual(self.db.execute('SELECT COUNT(*) AS n FROM nova_social_migrations').fetchone()['n'],1)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--postgres-bin',required=True)
    parser.add_argument('--local-worker',action='store_true')
    args=parser.parse_args()
    if not args.local_worker:
        raise SystemExit(subprocess.run([sys.executable,'-B',str(Path(__file__).resolve()),
            '--postgres-bin',args.postgres_bin,'--local-worker'],
            env={'PATH':'/usr/bin:/bin','LC_ALL':'C'}).returncode)
    harness.PG_BIN=Path(args.postgres_bin).resolve()
    PostgreSQLMessagingTests.__unittest_skip__=False
    names=[name for name in dir(MessagingContract) if name.startswith('test_')]
    names+=['test_concurrent_migration_and_startup','test_failed_migration_rollback']
    suite=unittest.TestSuite(PostgreSQLMessagingTests(name) for name in names)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())

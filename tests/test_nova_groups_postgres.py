"""Group contract on an owned disposable PostgreSQL cluster; no external DSN."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_billing_postgres as harness
from test_nova_groups import GroupContract
from services.nova_profile_schema import migrate_nova_profiles
from services.nova_chat_schema import migrate_nova_chat
from services.nova_group_schema import migrate_nova_groups


@unittest.skipUnless(harness.PG_BIN,'Opt-in disposable local PostgreSQL only')
class PostgreSQLGroupTests(GroupContract,harness.PostgresMigrationTests):
    postgres=True

    def setUp(self):
        super().setUp()
        self.connect=self.ns['get_db']
        migrate_nova_profiles(self.db,True)
        self.prepare_groups()

    def fresh(self,prefix):
        schema=prefix+self.schema
        self.db.execute('CREATE SCHEMA '+schema);self.db.commit()
        def connect():
            db=self.connect();db.execute('SET search_path TO '+schema)
            return db
        db=connect();db.execute('CREATE TABLE users(id INTEGER PRIMARY KEY)');db.commit()
        migrate_nova_profiles(db,True);migrate_nova_chat(db,True);db.close()
        return connect

    def test_concurrent_initial_migration_and_startup(self):
        connect=self.fresh('fresh_')
        def migrate(_):
            db=connect()
            try:migrate_nova_groups(db,True)
            finally:db.close()
        with ThreadPoolExecutor(3) as pool:list(pool.map(migrate,range(3)))
        db=connect()
        self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM nova_social_migrations').fetchone()['n'],3)
        db.close()
        self.ns['init_db']();self.ns['init_db']()

    def test_failed_migration_rolls_back(self):
        connect=self.fresh('failure_')
        db=connect()
        try:
            db.execute('CREATE TABLE nova_chat_events(id INTEGER PRIMARY KEY)');db.commit()
            with self.assertRaises(Exception):migrate_nova_groups(db,True)
            self.assertEqual(db.execute('SELECT COUNT(*) AS n FROM nova_social_migrations').fetchone()['n'],2)
            self.assertEqual(db.execute("SELECT COUNT(*) AS n FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='nova_chat_conversations' AND column_name='name'").fetchone()['n'],0)
        finally:db.close()


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
    PostgreSQLGroupTests.__unittest_skip__=False
    names=[n for n in dir(GroupContract) if n.startswith('test_')]
    names+=['test_concurrent_initial_migration_and_startup','test_failed_migration_rolls_back']
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(PostgreSQLGroupTests(n) for n in names))
    raise SystemExit(not result.wasSuccessful())

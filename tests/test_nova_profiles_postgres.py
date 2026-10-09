"""Opt-in local PostgreSQL profile tests using the existing disposable harness.

Run: venv/bin/python -B tests/test_nova_profiles_postgres.py --postgres-bin /path/to/bin
No external database URL or application startup is used.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_billing_postgres as harness
from services.nova_profile_schema import migrate_nova_profiles
from services.nova_profiles import claim_profile, ProfileError


@unittest.skipUnless(harness.PG_BIN, 'Opt-in disposable PostgreSQL only')
class ProfilePostgresTests(harness.PostgresMigrationTests):
    def test_profile_postgres(self):
        get_db = self.ns['get_db']
        def migrate(_):
            db = get_db()
            try:
                migrate_nova_profiles(db, postgres=True)
            finally:
                db.close()
        with ThreadPoolExecutor(2) as executor:
            list(executor.map(migrate, [1, 2]))
        def claim(uid):
            try:
                claim_profile(get_db, uid, 'Shared', postgres=True)
                return 200
            except ProfileError as error:
                return error.status
        with ThreadPoolExecutor(2) as executor:
            self.assertEqual(sorted(executor.map(claim, [1,2])), [200,409])
        migrate_nova_profiles(self.db, postgres=True)
        self.assertEqual(self.db.execute('SELECT COUNT(*) AS n FROM nova_profiles').fetchone()['n'],1)
        for sql in ["INSERT INTO nova_profiles(user_id,handle,display_name) VALUES(99,'orphan','Name')", "INSERT INTO nova_profiles(user_id,handle,display_name) VALUES(3,'UPPER','Name')"]:
            with self.assertRaises(sqlite3.IntegrityError): self.db.execute(sql)
        # Real startup initializes billing and profiles; repeat is safe.
        self.ns['init_db']()
        self.ns['init_db']()

    def test_profile_migration_rollback(self):
        self.db.execute('CREATE TABLE nova_profiles(id INTEGER PRIMARY KEY)')
        self.db.commit()
        with self.assertRaises(Exception): migrate_nova_profiles(self.db, postgres=True)
        self.assertIsNone(self.db.execute("SELECT to_regclass('nova_social_migrations') AS name").fetchone()['name'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--postgres-bin', required=True)
    parser.add_argument('--local-worker', action='store_true')
    args = parser.parse_args()
    if not args.local_worker:
        raise SystemExit(subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()),
            '--postgres-bin', args.postgres_bin, '--local-worker'],
            env={'PATH':'/usr/bin:/bin','LC_ALL':'C'}).returncode)
    harness.PG_BIN = Path(args.postgres_bin).resolve()
    # Base harness is skipped on import; enable only this explicit local runner.
    ProfilePostgresTests.__unittest_skip__ = False
    suite = unittest.TestSuite(ProfilePostgresTests(name) for name in
        ('test_profile_postgres', 'test_profile_migration_rollback'))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())

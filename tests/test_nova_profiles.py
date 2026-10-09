"""Isolated profile tests: no app import, dotenv, providers or real databases."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import tempfile
import unittest
from flask import Flask
from flask_login import LoginManager, UserMixin
from services.nova_profile_schema import migrate_nova_profiles
from services.nova_profiles import canonicalize_handle, claim_profile, get_profile, update_profile, ProfileError
from services.nova_profile_routes import register_nova_profiles


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'profiles.db'
        db = self.connect()
        db.execute('CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT, email TEXT, password_hash TEXT)')
        db.executemany('INSERT INTO users VALUES(?,?,?,?)', [(1,'Original Name','private@example.test','private-hash'),(2,'Other','other@example.test','hash')])
        db.commit()
        migrate_nova_profiles(db)
        db.close()
        self.app = Flask(__name__)
        self.app.secret_key = 'synthetic-test-only'
        manager = LoginManager(self.app)
        class User(UserMixin):
            def __init__(self, uid): self.id = uid
        manager.user_loader(lambda uid: User(uid))
        def guard(name):
            handle = open(Path(self.temp.name) / name, 'a+')
            handle.seek(0)
            return handle
        register_nova_profiles(self.app, self.connect, guard)
        self.client = self.app.test_client()

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        return db

    def login(self):
        with self.client.session_transaction() as session:
            session['_user_id'] = '1'
            session['csrf_token'] = 'synthetic-csrf'

    def patch(self, body):
        return self.client.patch('/api/nova-chat/profile', json=body, headers={'X-CSRF-Token':'synthetic-csrf'})

    def test_canonical_validation(self):
        self.assertEqual(canonicalize_handle('Alice_123'), 'alice_123')
        for value in ['ab','x'*31,'abc-def','éclair',' alice','alice@','admin','NOVA','nova_support',None,12]:
            with self.subTest(value=value), self.assertRaises(ProfileError): canonicalize_handle(value)

    def test_claim_privacy_and_no_account_changes(self):
        profile = claim_profile(self.connect, 1, 'Alice')
        self.assertEqual(profile['handle'], 'alice')
        self.assertFalse(profile['discoverable'])
        self.assertFalse(profile['allow_group_invites'])
        self.assertNotIn('user_id', profile)
        self.assertNotIn('email', profile)
        self.assertNotIn('password_hash', profile)
        db = self.connect()
        self.assertEqual(db.execute('SELECT username FROM users WHERE id=1').fetchone()[0], 'Original Name')
        db.close()

    def test_duplicate_and_concurrent_claim(self):
        def attempt(uid):
            try: claim_profile(self.connect, uid, 'shared'); return 200
            except ProfileError as error: return error.status
        with ThreadPoolExecutor(2) as executor:
            self.assertEqual(sorted(executor.map(attempt, [1,2])), [200,409])

    def test_anonymous_json_and_cache(self):
        for method, path in [('get','profile'),('patch','profile'),('get','username-availability?handle=alice')]:
            response = getattr(self.client, method)('/api/nova-chat/' + path)
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json['error'], 'unauthorized')
            self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_empty_get_is_read_only_and_free(self):
        self.login()
        self.assertEqual(self.client.get('/api/nova-chat/profile').json, {'ok':True,'profile':None})
        self.assertIsNone(get_profile(self.connect, 1))
        # Fixture has no subscriptions or AI tables: the routes cannot depend on them.
        self.assertEqual(self.patch({'handle':'alice'}).status_code, 200)
        self.assertEqual(self.client.get('/api/nova-chat/profile').json['profile']['handle'], 'alice')

    def test_csrf_and_allowed_updates(self):
        self.login()
        self.assertEqual(self.client.patch('/api/nova-chat/profile',json={'handle':'alice'}).status_code,403)
        self.assertEqual(self.patch({'handle':'alice'}).status_code,200)
        result = self.patch({'display_name':' Alice ', 'discoverable':True, 'allow_group_invites':True})
        self.assertEqual(result.json['profile']['display_name'], 'Alice')
        self.assertTrue(result.json['profile']['discoverable'])
        for field in ['email','password_hash','user_id','status','id','username']:
            self.assertEqual(self.patch({field:'forbidden'}).status_code,400)
        self.assertEqual(self.patch({'discoverable':1}).status_code,400)
        self.assertNotIn('private@example', str(result.json))

    def test_availability_rate_limit(self):
        self.login()
        url = '/api/nova-chat/username-availability?handle=Alice'
        self.assertTrue(self.client.get(url).json['available'])
        claim_profile(self.connect,1,'alice')
        self.assertFalse(self.client.get(url).json['available'])
        for _ in range(28): self.assertEqual(self.client.get(url).status_code,200)
        self.assertEqual(self.client.get(url).status_code,429)

    def test_migration_idempotence_and_constraints(self):
        claim_profile(self.connect,1,'alice')
        db = self.connect()
        migrate_nova_profiles(db)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM nova_social_migrations').fetchone()[0],1)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM nova_profiles').fetchone()[0],1)
        for sql in ["INSERT INTO nova_profiles(user_id,handle,display_name) VALUES(99,'valid','Name')", "INSERT INTO nova_profiles(user_id,handle,display_name) VALUES(2,'INVALID','Name')", 'DELETE FROM users WHERE id=1']:
            with self.assertRaises(sqlite3.IntegrityError): db.execute(sql)
            db.rollback()
        db.close()

    def test_migration_failure_rolls_back(self):
        db = sqlite3.connect(':memory:')
        db.row_factory = sqlite3.Row
        db.execute('CREATE TABLE nova_profiles(id INTEGER)')
        with self.assertRaises(sqlite3.OperationalError): migrate_nova_profiles(db)
        self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='nova_social_migrations'").fetchone())
        db.close()

    def test_suspended_and_oversized(self):
        claim_profile(self.connect,1,'alice')
        db = self.connect(); db.execute("UPDATE nova_profiles SET status='suspended'"); db.commit(); db.close()
        with self.assertRaises(ProfileError) as error: update_profile(self.connect,1,{'display_name':'Changed'})
        self.assertEqual(error.exception.status,403)
        self.login()
        self.assertEqual(self.patch({'display_name':'x'*5000}).status_code,413)


if __name__ == '__main__': unittest.main()

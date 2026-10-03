"""Isolated startup and OAuth regressions; no app import or external services."""
import ast
from contextlib import closing
import hmac
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch
from flask import Flask, jsonify, request, session

ROOT = Path(__file__).resolve().parents[1]


class OAuthStateTests(unittest.TestCase):
    def setUp(self):
        app = Flask('oauth_state_test')
        app.secret_key = 'synthetic-only'
        self.finish = Mock(side_effect=RuntimeError('Synthetic token exchange stop'))
        tree = ast.parse((ROOT / 'app.py').read_text())
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'google_oauth_callback')
        node.decorator_list = []
        ns = dict(session=session, request=request, jsonify=jsonify, hmac=hmac,
                  url_for=lambda *a, **k: 'https://example.invalid/callback',
                  finish_authorization=self.finish, app=app)
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'isolated_callback', 'exec'), ns)
        app.add_url_rule('/callback', view_func=ns[node.name])
        self.client = app.test_client()
        self.app = app

    def seed(self):
        with self.client.session_transaction() as s:
            s['google_oauth_state'] = 'expected'
            s['google_oauth_code_verifier'] = 'synthetic-verifier'

    def test_missing_state_rejected(self):
        self.seed()
        self.assertEqual(self.client.get('/callback').status_code, 403)
        self.finish.assert_not_called()

    def test_missing_session_state_rejected(self):
        self.assertEqual(self.client.get('/callback?state=expected').status_code, 403)
        self.finish.assert_not_called()

    def test_mismatch_consumes_state_and_verifier(self):
        self.seed()
        self.assertEqual(self.client.get('/callback?state=wrong').status_code, 403)
        self.assertEqual(self.client.get('/callback?state=expected').status_code, 403)
        self.finish.assert_not_called()
        with self.client.session_transaction() as s:
            self.assertNotIn('google_oauth_state', s)
            self.assertNotIn('google_oauth_code_verifier', s)

    def test_valid_state_enters_exchange_once_and_replay_rejected(self):
        self.seed()
        with patch.object(self.app.logger, 'exception'):
            self.assertEqual(self.client.get('/callback?state=expected').status_code, 400)
        self.assertEqual(self.finish.call_count, 1)
        self.assertEqual(self.finish.call_args.args[1], 'expected')
        self.assertEqual(self.finish.call_args.args[3], 'synthetic-verifier')
        self.assertEqual(self.client.get('/callback?state=expected').status_code, 403)
        self.assertEqual(self.finish.call_count, 1)

    def test_missing_verifier_rejected(self):
        self.seed()
        with self.client.session_transaction() as s:
            s.pop('google_oauth_code_verifier')
        self.assertEqual(self.client.get('/callback?state=expected').status_code, 403)
        self.finish.assert_not_called()


class WorkspaceStartupTests(unittest.TestCase):
    def test_real_sqlite_startup_creates_workspace_and_repeats(self):
        # Execute definitions only, so no environment config or production DSN.
        tree = ast.parse((ROOT / 'database.py').read_text())
        names = {'init_db', 'init_sqlite_db'}
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'test.sqlite'
            def connect():
                db = sqlite3.connect(path)
                db.row_factory = sqlite3.Row
                db.execute('PRAGMA foreign_keys=ON')
                return db
            ns = dict(sqlite3=sqlite3, DB_PATH=path, USE_POSTGRES=False, get_db=connect)
            exec(compile(ast.Module(body=nodes, type_ignores=[]), 'isolated_startup', 'exec'), ns)
            ns['init_db']()
            ns['init_db']()
            with closing(connect()) as db:
                names = {r['name'] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                self.assertTrue({'workspace_proposals', 'workspace_requests', 'apple_account_tokens'} <= names)
                self.assertEqual([r['id'] for r in db.execute('SELECT id FROM billing_migrations ORDER BY id')], [1, 2])

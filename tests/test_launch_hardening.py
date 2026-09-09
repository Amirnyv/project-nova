"""Isolated launch checks: never import app.py, load .env, or contact providers."""
import ast
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import tempfile
import time
import unittest
from functools import wraps
from types import SimpleNamespace
from unittest.mock import Mock, patch

from flask import Flask, Response, jsonify, make_response, redirect, request, session, stream_with_context, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, logout_user

ROOT = Path(__file__).resolve().parents[1]
TREE = ast.parse((ROOT / 'app.py').read_text())
FUNCTIONS = {
    'local_guard_file', 'acquire_chat_guard', 'serialize_chat', 'csrf_token',
    'csrf_context', 'protect_browser_mutations', 'limit_auth_requests', 'chat', 'logout',
}
CONSTANTS = {'MAX_CHAT_MESSAGE_LENGTH', 'MAX_AI_OUTPUT_TOKENS', 'AGENT_INSTRUCTIONS'}


class FakeStream:
    def __init__(self, events):
        self.events = iter(events)
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self):
        event = next(self.events)
        if isinstance(event, Exception):
            raise event
        return event

    def close(self):
        self.closed = True


def result():
    return SimpleNamespace(id='resp_test', usage=SimpleNamespace(input_tokens=120, output_tokens=30),
                           to_dict=lambda: {'output': []})


def events(terminal='response.completed'):
    return [SimpleNamespace(type='response.created', response=SimpleNamespace(id='resp_test')),
            SimpleNamespace(type='response.output_text.delta', delta='Hello'),
            SimpleNamespace(type=terminal, response=result())]


class HardeningTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.app = Flask('isolated_hardening')
        self.app.secret_key = 'synthetic-test-session-secret'
        self.app.testing = True
        manager = LoginManager(self.app)

        class User(UserMixin):
            def __init__(self, uid):
                self.id = uid

        manager.user_loader(lambda uid: User(uid))
        self.provider = Mock()
        self.stream = FakeStream(events())
        self.provider.responses.create.return_value = self.stream
        self.provider.responses.retrieve.return_value = result()
        self.ns = dict(
            app=self.app, os=os, fcntl=fcntl, hashlib=hashlib, hmac=hmac, secrets=secrets,
            tempfile=SimpleNamespace(gettempdir=lambda: self.directory.name), time=time, json=json,
            wraps=wraps, sqlite3=sqlite3, USE_POSTGRES=False, request=request, session=session,
            jsonify=jsonify, make_response=make_response, Response=Response, stream_with_context=stream_with_context,
            current_user=current_user, login_required=login_required, logout_user=logout_user,
            redirect=redirect, url_for=url_for, client=self.provider,
            check_ai_usage_limit=Mock(return_value={'allowed': True, 'plan': 'max', 'remaining': 100000}),
            get_active_subscription=Mock(return_value={'status': 'active', 'plan': 'max'}),
            create_conversation=Mock(return_value=1), get_conversation_messages=Mock(return_value=[]),
            save_conversation_message=Mock(), record_ai_usage=Mock(), get_trade_history=Mock(return_value=[]),
        )
        selected = []
        for node in TREE.body:
            if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS:
                selected.append(node)
            elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in CONSTANTS for t in node.targets):
                selected.append(node)
        exec(compile(ast.Module(body=selected, type_ignores=[]), 'isolated_app', 'exec'), self.ns)
        for endpoint in ['login', 'signup', 'forgot_password', 'reset_password', 'add_project',
                         'save_project_notes', 'create_project_task', 'update_project_task',
                         'delete_project_task', 'upload_project_file', 'delete_project_file', 'delete_conversation',
                         'create_checkout_session', 'create_portal_session', 'stripe_webhook']:
            self.app.add_url_rule('/test/' + endpoint, endpoint, lambda: jsonify(ok=True), methods=['GET', 'POST', 'PATCH', 'DELETE'])
        self.web = self.new_client('1')

    def new_client(self, uid):
        web = self.app.test_client()
        with web.session_transaction() as state:
            state['_user_id'] = uid
            state['_fresh'] = True
            state['csrf_token'] = 'test-csrf'
        return web

    def chat(self, web=None, buffered=True, **payload):
        return (web or self.web).post('/chat', json={'message': 'Hello Nova', **payload},
                                     headers={'X-CSRF-Token': 'test-csrf'}, buffered=buffered)

    def test_stream_and_twenty_message_context(self):
        self.ns['get_conversation_messages'].return_value = [{'role': 'user', 'content': str(i)} for i in range(30)]
        response = self.chat()
        self.assertEqual(response.status_code, 200)
        self.assertIn('"type": "done"', response.text)
        args = self.provider.responses.create.call_args.kwargs
        self.assertEqual(args['max_output_tokens'], 4096)
        self.assertTrue(args['stream'])
        self.assertEqual([m['content'] for m in args['input'] if m['role'] == 'user'], [str(i) for i in range(10, 30)] + ['Hello Nova'])
        self.ns['record_ai_usage'].assert_called_once_with(1, 1, 'gpt-5-mini', 120, 30)
        self.assertTrue(self.stream.closed)

    def test_disconnect_accounts_and_keeps_guard_until_close(self):
        response = self.chat(buffered=False)
        self.ns['record_ai_usage'].assert_not_called()
        self.assertIsNone(self.ns['acquire_chat_guard'](1))
        response.close()
        self.ns['record_ai_usage'].assert_called_once_with(1, 1, 'gpt-5-mini', 120, 30)
        release = self.ns['acquire_chat_guard'](1)
        self.assertIsNotNone(release)
        release()
        self.assertTrue(self.stream.closed)

    def test_busy_request_does_not_check_usage_or_call_ai(self):
        release = self.ns['acquire_chat_guard'](1)
        try:
            response = self.chat()
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.json['error'], 'generation_in_progress')
            self.ns['check_ai_usage_limit'].assert_not_called()
            self.provider.responses.create.assert_not_called()
            other = self.ns['acquire_chat_guard'](2)
            self.assertIsNotNone(other)
            other()
        finally:
            release()

    @unittest.skipUnless(hasattr(os, 'fork'), 'POSIX lock test')
    def test_lock_is_shared_with_another_process(self):
        release = self.ns['acquire_chat_guard'](1)
        # Separate open file descriptions must contend across workers.
        pid = os.fork()
        if pid == 0:
            blocked = self.ns['acquire_chat_guard'](1) is None
            os._exit(0 if blocked else 1)
        _, status = os.waitpid(pid, 0)
        release()
        self.assertEqual(os.waitstatus_to_exitcode(status), 0)

    def test_postgres_guard_uses_session_lock(self):
        db = Mock()
        db.execute.return_value.fetchone.return_value = {'acquired': True}
        self.ns.update(USE_POSTGRES=True, get_db=Mock(return_value=db))
        release = self.ns['acquire_chat_guard'](1)
        db.commit.assert_called_once()
        release()
        db.close.assert_called_once()
        db.reset_mock()
        db.execute.return_value.fetchone.return_value = {'acquired': False}
        self.assertIsNone(self.ns['acquire_chat_guard'](1))
        db.close.assert_called_once()

    def test_invalid_message_releases_guard(self):
        for message in ['x' * 16001, 42, None]:
            self.assertEqual(self.chat(message=message).status_code, 400)
        self.provider.responses.create.assert_not_called()
        release = self.ns['acquire_chat_guard'](1)
        self.assertIsNotNone(release)
        release()

    def test_existing_access_denials_and_market_command(self):
        self.ns['get_active_subscription'].return_value = {'plan': 'pro', 'status': 'active'}
        self.assertEqual(self.chat(agent_mode='coding').status_code, 403)
        self.ns['check_ai_usage_limit'].return_value = {'allowed': False, 'reason': 'usage_limit_reached'}
        self.assertEqual(self.chat().status_code, 429)
        self.ns['check_ai_usage_limit'].return_value = {'allowed': False, 'reason': 'subscription_required'}
        self.assertEqual(self.chat().status_code, 402)
        self.ns['check_ai_usage_limit'].return_value = {'allowed': True}
        response = self.chat(message='trade history', agent_mode='market')
        self.assertIn('No paper trades', response.json['reply'])
        self.provider.responses.create.assert_not_called()

    def test_incomplete_and_broken_stream_usage(self):
        for terminal in ['response.incomplete', 'response.failed']:
            self.provider.responses.create.return_value = FakeStream(events(terminal))
            self.chat().close()
        self.assertEqual(self.ns['record_ai_usage'].call_count, 2)
        self.ns['record_ai_usage'].reset_mock()
        self.provider.responses.create.return_value = FakeStream(events()[:2] + [RuntimeError('synthetic upstream failure')])
        response = self.chat()
        self.assertIn('"type": "error"', response.text)
        self.provider.responses.retrieve.assert_called_with('resp_test', timeout=10)
        self.ns['record_ai_usage'].assert_called_once()

    def test_deleted_content_does_not_prevent_accounting(self):
        def save(*args, **kwargs):
            if args[2] == 'assistant':
                raise sqlite3.IntegrityError('synthetic deleted conversation')
        self.ns['save_conversation_message'].side_effect = save
        self.chat().close()
        self.ns['record_ai_usage'].assert_called_once()

    def test_csrf_form_json_and_multipart(self):
        for endpoint in ['login', 'signup', 'forgot_password', 'reset_password', 'add_project',
                         'save_project_notes', 'create_project_task', 'upload_project_file']:
            url = '/test/' + endpoint
            self.assertEqual(self.web.post(url, data={}).status_code, 403)
            self.assertEqual(self.web.post(url, data={'csrf_token': 'test-csrf'}, content_type='multipart/form-data').status_code, 200)
        for endpoint in ['update_project_task', 'delete_project_task', 'delete_project_file', 'delete_conversation']:
            url = '/test/' + endpoint
            self.assertEqual(self.web.delete(url).status_code, 403)
            self.assertEqual(self.web.delete(url, headers={'X-CSRF-Token': 'test-csrf'}).status_code, 200)
        self.assertEqual(self.web.post('/chat', json={'message': 'test'}).status_code, 403)
        self.assertEqual(self.web.post('/chat', json={}, headers={'X-CSRF-Token': 'é'}).status_code, 403)

    def test_billing_hooks_unchanged_and_logout_post_only(self):
        for endpoint in ['create_checkout_session', 'create_portal_session', 'stripe_webhook']:
            self.assertEqual(self.web.post('/test/' + endpoint).status_code, 200)
        self.assertEqual(self.web.get('/logout').status_code, 405)
        self.assertEqual(self.web.post('/logout').status_code, 403)
        self.assertEqual(self.web.post('/logout', data={'csrf_token': 'test-csrf'}).status_code, 302)
        with self.web.session_transaction() as state:
            self.assertNotIn('_user_id', state)

    def test_auth_rate_limits_shared_between_clients_and_expire(self):
        for endpoint, count in [('login', 10), ('signup', 5), ('forgot_password', 5), ('reset_password', 30)]:
            payload = {'csrf_token': 'test-csrf', 'email': 'test@example.invalid'}
            if endpoint == 'reset_password':
                payload.pop('email')
            for _ in range(count):
                self.assertEqual(self.web.post('/test/' + endpoint, data=payload).status_code, 200)
            other = self.new_client('2')
            response = other.post('/test/' + endpoint, data=payload)
            self.assertEqual(response.status_code, 429)
            self.assertGreater(int(response.headers['Retry-After']), 0)
        with patch.object(time, 'time', return_value=time.time() + 3700):
            self.assertEqual(self.web.post('/test/login', data={'csrf_token': 'test-csrf', 'email': 'test@example.invalid'}).status_code, 200)

    def test_secure_cookie_config_is_opt_in_for_local_http(self):
        node = next(n for n in TREE.body if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                    and ast.unparse(n.value.func) == 'app.config.update')
        for env, secure in [('development', False), ('production', True)]:
            ns = {'app': self.app, 'os': SimpleNamespace(getenv=lambda *args: env)}
            exec(compile(ast.Module(body=[node], type_ignores=[]), 'config', 'exec'), ns)
            self.assertEqual(self.app.config['SESSION_COOKIE_SECURE'], secure)
            self.assertFalse(self.app.debug)
            self.assertTrue(self.app.config['SESSION_COOKIE_HTTPONLY'])
            self.assertEqual(self.app.config['SESSION_COOKIE_SAMESITE'], 'Lax')

    def test_usage_insert_detaches_a_deleted_conversation(self):
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.execute('PRAGMA foreign_keys=ON')
        db.executescript('CREATE TABLE conversations(id INTEGER PRIMARY KEY, user_id INTEGER);'
                         'CREATE TABLE ai_usage(user_id INTEGER, conversation_id INTEGER REFERENCES conversations(id),'
                         'model TEXT,input_tokens INTEGER,output_tokens INTEGER,total_tokens INTEGER);')
        class Connection:
            def execute(self, *args): return db.execute(*args)
            def commit(self): db.commit()
            def close(self): pass
        node = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == 'record_ai_usage')
        ns = {'get_db': Connection}
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'usage', 'exec'), ns)
        ns['record_ai_usage'](1, 99, 'test', 120, 30)
        self.assertEqual(db.execute('SELECT conversation_id,total_tokens FROM ai_usage').fetchone(), (None, 150))


if __name__ == '__main__':
    unittest.main()

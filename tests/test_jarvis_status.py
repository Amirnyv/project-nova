"""Status endpoint isolation: no app startup, environment files, or providers."""
import ast
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from flask import Flask, jsonify
from flask_login import LoginManager, UserMixin, login_required
from services.jarvis_tools import JARVIS_TOOLS


class JarvisStatusTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask('status_test')
        self.app.config.update(TESTING=True, SECRET_KEY='synthetic-session-secret')
        manager = LoginManager(self.app)
        manager.login_view = 'login'
        self.app.add_url_rule('/login', 'login', lambda: 'Login')

        class User(UserMixin):
            def __init__(self, uid):
                self.id = uid

        manager.user_loader(lambda uid: User(uid))
        self.forbidden = {name: Mock(side_effect=AssertionError(name + ' must not run'))
                          for name in ['execute_jarvis_tool', 'get_db', 'record_ai_usage',
                                       'check_ai_usage_limit', 'routed_chat_stream',
                                       'routed_chat_completion', 'plan_jarvis_action']}
        self.namespace = dict(app=self.app, jsonify=jsonify, login_required=login_required,
                              JARVIS_TOOLS=JARVIS_TOOLS, **self.forbidden)
        tree = ast.parse((Path(__file__).resolve().parents[1] / 'app.py').read_text())
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'jarvis_status')
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'isolated_status', 'exec'), self.namespace)
        self.client = self.client_for('1')

    def client_for(self, uid):
        client = self.app.test_client()
        with client.session_transaction() as state:
            state['_user_id'] = uid
            state['_fresh'] = True
        return client

    def test_unauthenticated_requires_login(self):
        response = self.app.test_client().get('/api/jarvis/status')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers['Location'])
        self.assertIsNone(response.json)

    def test_authenticated_exact_safe_shape(self):
        response = self.client.get('/api/jarvis/status')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {
            'ok': True,
            'jarvis': {'tools_available': True, 'planner_available': True,
                       'confirmations_available': True, 'project_resolution_available': True},
            'capabilities': {
                'read_tools': sorted(['projects.list', 'projects.get', 'tasks.list', 'notes.get',
                                      'markets.quote', 'markets.analyze', 'portfolio.get', 'trades.history']),
                'write_tools': ['tasks.create', 'tasks.toggle'], 'destructive_tools': []},
            'confirmation_store': {'type': 'memory', 'production_ready': False}})

    def test_capabilities_come_from_registry_without_handlers_or_schemas(self):
        handler = Mock(side_effect=AssertionError('Must not execute'))
        registry = {'read': SimpleNamespace(name='example.read', risk_level='read', handler=handler),
                    'write': SimpleNamespace(name='example.write', risk_level='write', handler=handler)}
        with patch.dict(self.namespace, JARVIS_TOOLS=registry):
            self.assertEqual(self.client.get('/api/jarvis/status').json['capabilities'], {
                'read_tools': ['example.read'], 'write_tools': ['example.write'], 'destructive_tools': []})
        handler.assert_not_called()

    def test_no_execution_provider_usage_or_database_calls(self):
        from services import jarvis_tools, jarvis_planner
        with patch.object(jarvis_tools, 'execute_jarvis_tool') as execute, \
                patch.object(jarvis_tools, '_get_db') as db, \
                patch.object(jarvis_planner, '_routed_completion') as ai:
            self.assertEqual(self.client.get('/api/jarvis/status').status_code, 200)
            execute.assert_not_called()
            db.assert_not_called()
            ai.assert_not_called()
        for forbidden in self.forbidden.values():
            forbidden.assert_not_called()

    def test_no_environment_or_session_values_and_same_metadata_for_other_users(self):
        with patch.dict(os.environ, {'NOVA_TEST_SECRET': 'SYNTHETIC_ENV_SECRET'}):
            with self.client.session_transaction() as state:
                state['private_test_value'] = 'SYNTHETIC_PRIVATE_VALUE'
            response = self.client.get('/api/jarvis/status')
            self.assertNotIn('SYNTHETIC_ENV_SECRET', response.text)
            self.assertNotIn('SYNTHETIC_PRIVATE_VALUE', response.text)
            self.assertNotIn('synthetic-session-secret', response.text)
            self.assertEqual(response.json, self.client_for('222').get('/api/jarvis/status').json)

    def test_mutation_methods_not_allowed(self):
        for method in ['post', 'put', 'patch', 'delete']:
            self.assertEqual(getattr(self.client, method)('/api/jarvis/status').status_code, 405)


if __name__ == '__main__':
    unittest.main()

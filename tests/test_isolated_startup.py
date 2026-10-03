"""Gunicorn app-loading smoke test with a scrubbed environment and temporary DB."""
from pathlib import Path
import os
import subprocess
import sys
import unittest


class IsolatedStartupTests(unittest.TestCase):
    def test_gunicorn_import_and_authenticated_route_guards(self):
        root = Path(__file__).resolve().parents[1]
        code = '''
import sys, tempfile
from pathlib import Path
# Forbid outbound TCP connections; this smoke test must be offline.
def audit(event, args):
    if event == 'socket.connect':
        raise RuntimeError('Network forbidden during startup test')
sys.addaudithook(audit)
import dotenv
dotenv.load_dotenv = lambda *a, **k: False
import database
with tempfile.TemporaryDirectory() as temp:
    database.DB_PATH = Path(temp) / 'startup.sqlite'
    from gunicorn.util import import_app
    app = import_app('app:app')
    assert app.config['DEBUG'] is False
    assert app.config['SESSION_COOKIE_SECURE'] is True
    routes = {r.rule for r in app.url_map.iter_rules()}
    assert {'/api/billing/apple/account-token', '/api/billing/apple/sync',
            '/api/billing/apple/notifications', '/api/workspace/prepare',
            '/api/workspace/confirm', '/chat'} <= routes
    response = app.test_client().get('/api/ai/usage')
    assert response.status_code in (302, 401)
    db = database.get_db()
    assert db.execute('SELECT COUNT(*) AS n FROM workspace_proposals').fetchone()['n'] == 0
    db.close()
'''
        env = {'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1',
               'FLASK_SECRET_KEY': 'synthetic-startup-only', 'OPENAI_API_KEY': 'synthetic-unused',
               'DATABASE_URL': '', 'NOVA_ENV': 'production'}
        result = subprocess.run([sys.executable, '-B', '-c', code], cwd=root, env=env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

"""Isolated Jarvis tests: no app startup, .env loading, or external requests."""
import ast
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from services import jarvis_tools as tools
from services import jarvis_planner as planner

ROOT = Path(__file__).resolve().parents[1]


def isolated_agent(filename, names, **context):
    """Execute existing helpers without their provider/database module imports."""
    tree = ast.parse((ROOT / filename).read_text())
    nodes = [node for node in tree.body
             if isinstance(node, ast.FunctionDef) and node.name in names]
    if {node.name for node in nodes} != set(names):
        raise AssertionError('Existing helper was renamed')
    module = types.ModuleType(filename)
    module.__dict__.update(context)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, 'exec'), module.__dict__)
    return module


class JarvisToolsTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'jarvis.sqlite'
        db = self.connect()
        db.executescript('''
            CREATE TABLE projects (id INTEGER PRIMARY KEY, user_id INTEGER,
                name TEXT, description TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE project_tasks (id INTEGER PRIMARY KEY, user_id INTEGER,
                project_id INTEGER REFERENCES projects(id), title TEXT, completed INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE project_notes (id INTEGER PRIMARY KEY, user_id INTEGER,
                project_id INTEGER UNIQUE REFERENCES projects(id), content TEXT);
            CREATE TABLE portfolios (id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE, cash REAL);
            CREATE TABLE positions (id INTEGER PRIMARY KEY, user_id INTEGER,
                symbol TEXT, shares REAL, average_price REAL);
            CREATE TABLE trades (id INTEGER PRIMARY KEY, user_id INTEGER, action TEXT,
                symbol TEXT, shares REAL, price REAL, total REAL, created_at TEXT);
            INSERT INTO projects (id,user_id,name,description) VALUES
                (1,1,'Mine','Private'),(2,2,'Theirs','Secret'),(3,1,'Empty','');
            INSERT INTO project_tasks (id,user_id,project_id,title,completed) VALUES
                (1,1,1,'Mine',0),(2,2,2,'Secret',0);
            INSERT INTO project_notes VALUES (1,1,1,'My notes'),(2,2,2,'Secret notes');
            INSERT INTO portfolios VALUES (1,1,500),(2,2,900);
            INSERT INTO positions VALUES (1,1,'AAPL',2,100),(2,2,'MSFT',3,200);
            INSERT INTO trades VALUES (1,1,'buy','AAPL',2,100,200,'2026-01-01'),
                (2,2,'buy','MSFT',3,200,600,'2026-01-01');
        ''')
        db.close()
        self.addCleanup(patch.stopall)
        patch.object(tools, '_get_db', self.connect).start()
        project = isolated_agent('agents/project_agent.py', ['get_projects'], get_db=self.connect)
        portfolio_tree = ast.parse((ROOT / 'agents/portfolio_agent.py').read_text())
        starting_cash = next(ast.literal_eval(node.value) for node in portfolio_tree.body
                             if isinstance(node, ast.Assign)
                             and any(isinstance(t, ast.Name) and t.id == 'STARTING_CASH'
                                     for t in node.targets))
        portfolio = isolated_agent('agents/portfolio_agent.py', ['get_trade_history'],
                                   get_db=self.connect, STARTING_CASH=starting_cash)
        self.market = types.ModuleType('agents.stock_agent')
        self.market.get_market_quote = Mock(return_value={'symbol': 'AAPL', 'price': 123})
        self.market.analyze_stock = Mock(return_value={'symbol': 'AAPL', 'score': 70})
        patch.dict(sys.modules, {'agents.project_agent': project,
                                'agents.portfolio_agent': portfolio,
                                'agents.stock_agent': self.market}).start()

    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys = ON')
        return db

    def query(self, sql):
        db = self.connect()
        try:
            return [dict(row) for row in db.execute(sql).fetchall()]
        finally:
            db.close()

    def run_tool(self, name, args=None, user=1, confirmed=False):
        result = tools.execute_jarvis_tool(user, name, args if args is not None else {}, confirmed=confirmed)
        self.assertEqual(set(result), {'ok', 'tool', 'data' if result['ok'] else 'error'})
        json.dumps(result, allow_nan=False)
        return result

    def test_registry_and_detached_definitions(self):
        expected = {'projects.list','projects.get','tasks.list','tasks.create','tasks.toggle',
                    'notes.get','markets.quote','markets.analyze','portfolio.get','trades.history'}
        definitions = planner.get_jarvis_tool_definitions()
        self.assertEqual(set(tools.JARVIS_TOOLS), expected)
        json.dumps(definitions)
        for definition in definitions:
            self.assertNotIn('handler', definition)
            self.assertNotIn('user_id', definition['parameters']['properties'])
            self.assertIs(type(definition['requires_confirmation']), bool)
            self.assertIn(definition['risk_level'], {'read', 'write'})
            if definition['risk_level'] == 'write':
                self.assertTrue(definition['requires_confirmation'])
        definitions[1]['parameters']['properties'].clear()
        self.assertTrue(self.run_tool('projects.get', {'project_id': 1})['ok'])

    def test_unknown_and_malformed_arguments_never_reach_db(self):
        with patch.object(tools, '_get_db') as db:
            for name in ['shell.run', 'projects.delete', None, []]:
                self.assertEqual(self.run_tool(name)['error']['code'], 'unknown_tool')
            for args in [{}, {'project_id': True}, {'project_id': '1'}, {'project_id': -1},
                         {'project_id': 2**40}, {'project_id': 1, 'user_id': 2}, [],
                         {'project_id': 1, 'confirmed': True}]:
                self.assertEqual(self.run_tool('projects.get', args)['error']['code'], 'invalid_arguments')
            db.assert_not_called()

    def test_server_context_required(self):
        for user in [None, True, '1', 0, -1]:
            self.assertEqual(self.run_tool('projects.list', user=user)['error']['code'], 'invalid_context')
        self.assertEqual(self.run_tool('projects.list', confirmed='yes')['error']['code'], 'invalid_context')

    def test_project_list_and_get_are_scoped(self):
        self.assertEqual({p['id'] for p in self.run_tool('projects.list')['data']}, {1, 3})
        self.assertEqual(self.run_tool('projects.get', {'project_id': 1})['data']['name'], 'Mine')
        other = self.run_tool('projects.get', {'project_id': 2})
        missing = self.run_tool('projects.get', {'project_id': 999})
        self.assertEqual(other, missing)
        self.assertEqual(other['error']['code'], 'not_found')

    def test_tasks_and_notes_are_scoped(self):
        rows = self.run_tool('tasks.list', {'project_id': 1})['data']
        self.assertEqual([r['title'] for r in rows], ['Mine'])
        self.assertIs(rows[0]['completed'], False)
        self.assertEqual(self.run_tool('notes.get', {'project_id': 1})['data'], {'content': 'My notes'})
        self.assertEqual(self.run_tool('notes.get', {'project_id': 3})['data'], {'content': ''})
        for name in ['tasks.list', 'notes.get']:
            self.assertEqual(self.run_tool(name, {'project_id': 2})['error']['code'], 'not_found')

    def test_create_requires_confirmation_and_checks_ownership(self):
        args = {'project_id': 1, 'title': '  New task  '}
        with patch.object(tools, '_get_db') as db:
            self.assertEqual(self.run_tool('tasks.create', args)['error']['code'], 'confirmation_required')
            db.assert_not_called()
        created = self.run_tool('tasks.create', args, confirmed=True)
        self.assertTrue(created['ok'])
        self.assertEqual(created['data']['title'], 'New task')
        rows = self.query('SELECT * FROM project_tasks WHERE id = %d' % created['data']['id'])
        self.assertEqual((rows[0]['user_id'], rows[0]['project_id']), (1, 1))
        self.assertEqual(self.run_tool('tasks.create', {'project_id': 2, 'title': 'No'},
                                       confirmed=True)['error']['code'], 'not_found')
        self.assertEqual(len(self.query('SELECT * FROM project_tasks')), 3)

    def test_toggle_confirmation_ownership_and_repeat(self):
        args = {'project_id': 1, 'task_id': 1, 'completed': True}
        self.assertEqual(self.run_tool('tasks.toggle', args)['error']['code'], 'confirmation_required')
        for _ in range(2):
            self.assertTrue(self.run_tool('tasks.toggle', args, confirmed=True)['ok'])
        self.assertEqual(self.query('SELECT completed FROM project_tasks WHERE id=1')[0]['completed'], 1)
        for project, task in [(2, 2), (1, 2), (1, 999)]:
            self.assertEqual(self.run_tool('tasks.toggle', dict(args, project_id=project, task_id=task),
                                          confirmed=True)['error']['code'], 'not_found')
        self.assertEqual(self.query('SELECT completed FROM project_tasks WHERE id=2')[0]['completed'], 0)
        self.assertTrue(self.run_tool('tasks.toggle', dict(args, completed=False), confirmed=True)['ok'])

    def test_titles_symbols_and_boolean_validation(self):
        for title in ['', '   ', 'a'*501, 123]:
            self.assertEqual(self.run_tool('tasks.create', {'project_id': 1, 'title': title},
                                          confirmed=True)['error']['code'], 'invalid_arguments')
        for symbol in ['https://example.test/?apikey=secret', 'A'*33, '', 'AAPL\nMSFT']:
            self.assertEqual(self.run_tool('markets.quote', {'symbol': symbol})['error']['code'], 'invalid_arguments')
        self.market.get_market_quote.assert_not_called()
        self.assertEqual(self.run_tool('tasks.toggle', {'project_id': 1, 'task_id': 1, 'completed': 1},
                                      confirmed=True)['error']['code'], 'invalid_arguments')

    def test_portfolio_and_history_scoping_without_writes(self):
        result = self.run_tool('portfolio.get')['data']
        self.assertEqual(result['cash'], 500)
        self.assertEqual(set(result['positions']), {'AAPL'})
        self.assertEqual([r['symbol'] for r in self.run_tool('trades.history')['data']], ['AAPL'])
        self.assertEqual(self.run_tool('portfolio.get', user=3)['data'], {'cash': 10000.0, 'positions': {}})
        self.assertEqual(len(self.query('SELECT * FROM portfolios')), 2)

    def test_market_helpers_and_date_normalization(self):
        self.market.get_market_quote.return_value['timestamp'] = datetime(2026, 1, 1)
        quote = self.run_tool('markets.quote', {'symbol': ' AAPL '})
        self.assertEqual(quote['data']['timestamp'], '2026-01-01T00:00:00')
        self.market.get_market_quote.assert_called_once_with('AAPL')
        self.assertEqual(self.run_tool('markets.analyze', {'symbol': 'AAPL'})['data']['score'], 70)
        self.market.analyze_stock.assert_called_once_with('AAPL')

    def test_errors_and_logs_do_not_expose_upstream_details(self):
        secret = 'https://upstream.invalid/private?apikey=SYNTHETIC_TEST_SECRET'
        for behavior in ['exception', 'error_result']:
            self.market.get_market_quote.side_effect = RuntimeError(secret) if behavior == 'exception' else None
            self.market.get_market_quote.return_value = {'error': secret}
            with self.assertLogs(tools.logger, level='INFO') as logs:
                result = self.run_tool('markets.quote', {'symbol': 'AAPL'})
            self.assertEqual(result['error']['code'], 'tool_failed')
            text = json.dumps(result) + str(logs.output)
            for forbidden in ['apikey', 'SYNTHETIC_TEST_SECRET', 'upstream.invalid', 'Traceback']:
                self.assertNotIn(forbidden, text)

    def test_write_failure_rolls_back_and_closes(self):
        connection = Mock()
        connection.execute.side_effect = RuntimeError('private database path')
        with patch.object(tools, '_get_db', return_value=connection):
            result = self.run_tool('tasks.create', {'project_id': 1, 'title': 'Task'}, confirmed=True)
        self.assertEqual(result['error']['code'], 'tool_failed')
        connection.rollback.assert_called_once()
        connection.close.assert_called_once()
        connection.commit.assert_not_called()

    def test_planner_rejects_model_authority_and_revalidates(self):
        call = {'name': 'tasks.create', 'arguments': {'project_id': 1, 'title': 'Planned'}}
        with patch.object(tools, '_get_db') as db:
            validated = planner.validate_jarvis_tool_call(call)
            self.assertTrue(validated['ok'])
            db.assert_not_called()
        for extra in [{'user_id': 2}, {'confirmed': True}]:
            self.assertEqual(planner.execute_jarvis_tool_call(1, dict(call, **extra))['error']['code'], 'invalid_call')
        self.assertEqual(planner.execute_jarvis_tool_call(1, call)['error']['code'], 'confirmation_required')
        self.assertTrue(planner.execute_jarvis_tool_call(1, validated['data'], confirmed=True)['ok'])
        validated['data']['arguments']['user_id'] = 2
        self.assertEqual(planner.execute_jarvis_tool_call(1, validated['data'], confirmed=True)['error']['code'], 'invalid_arguments')


if __name__ == '__main__':
    unittest.main()

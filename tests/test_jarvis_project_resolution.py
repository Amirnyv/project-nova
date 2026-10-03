"""Bounded owned-project resolution; temporary SQLite and no provider calls."""
import json
import unittest
from unittest.mock import Mock, patch

from services import jarvis_planner as planner
from services import jarvis_confirmations as confirmations
import test_jarvis_tools


class ProjectResolutionTests(unittest.TestCase):
    def setUp(self):
        fixture = test_jarvis_tools.JarvisToolsTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.store = confirmations.PendingActions()
        patcher = patch.object(confirmations, 'pending_actions', self.store)
        patcher.start()
        self.addCleanup(patcher.stop)

    def context(self, tool, arguments):
        messages = planner.jarvis_result_context(1, {'action': 'tool', 'tool': tool,
                                                   'arguments': arguments}, conversation_id=10)
        return json.loads(messages[-1]['content'].split('\n', 1)[1])

    def insert_project(self, uid, name):
        db = self.fixture.connect()
        db.execute('INSERT INTO projects (user_id,name,description) VALUES (?, ?, ?)', (uid, name, ''))
        db.commit()
        db.close()

    def test_exact_case_whitespace_normalization_and_correct_id(self):
        for name in ['Mine', 'mINE', '  MINE  ']:
            result = planner.resolve_jarvis_project(1, 'tasks.list', {'project_name': name})
            self.assertTrue(result['ok'])
            self.assertEqual(result['data']['arguments'], {'project_id': 1})
        self.insert_project(1, 'My   Test Project')
        result = planner.resolve_jarvis_project(1, 'tasks.list', {'project_name': 'my test  project'})
        self.assertEqual(result['project']['name'], 'My   Test Project')

    def test_duplicates_only_list_matching_owned_projects(self):
        self.insert_project(1, 'MINE')
        self.insert_project(2, 'Mine')
        result = self.context('tasks.list', {'project_name': 'mine'})
        self.assertEqual(result['error']['code'], 'project_ambiguous')
        self.assertEqual(len(result['matches']), 2)
        self.assertEqual({p['name'] for p in result['matches']}, {'Mine', 'MINE'})
        self.assertEqual(self.store._actions, {})

    def test_missing_cross_user_and_partial_names_do_not_resolve(self):
        for name in ['Missing', 'Theirs', 'Min']:
            result = self.context('tasks.create', {'project_name': name, 'title': 'Essay'})
            self.assertEqual(result['error']['code'], 'project_not_found')
            self.assertEqual(result['matches'], [])
        self.assertEqual(self.store._actions, {})

    def test_other_users_duplicate_does_not_make_owned_name_ambiguous(self):
        self.insert_project(2, 'Mine')
        self.assertTrue(self.context('tasks.list', {'project_name': 'Mine'})['ok'])

    def test_tasks_list_from_name_with_one_discovery_and_one_intended_action(self):
        with patch.object(planner, 'execute_jarvis_tool', wraps=planner.execute_jarvis_tool) as execute:
            result = self.context('tasks.list', {'project_name': 'Mine'})
        self.assertEqual([c.args[1] for c in execute.call_args_list], ['projects.list', 'tasks.list'])
        self.assertEqual([t['title'] for t in result['data']], ['Mine'])
        self.assertEqual(result['project'], {'id': 1, 'name': 'Mine'})

    def test_named_write_requires_confirmation_executes_once_and_replay_fails(self):
        result = self.context('tasks.create', {'project_name': 'Mine', 'title': 'Study chapter 4'})
        self.assertEqual(result['error']['code'], 'confirmation_required')
        self.assertEqual(result['pending']['arguments'], {'project_id': 1, 'title': 'Study chapter 4'})
        self.assertEqual(len(self.fixture.query('SELECT * FROM project_tasks')), 2)
        self.assertTrue(self.store.resolve(1, 10, 'confirm')['ok'])
        self.assertEqual(len(self.fixture.query('SELECT * FROM project_tasks')), 3)
        self.assertFalse(self.store.resolve(1, 10, 'confirm')['ok'])
        self.assertEqual(len(self.fixture.query('SELECT * FROM project_tasks')), 3)

    def test_injected_ids_and_identity_rejected_before_discovery(self):
        for args in [{'project_name': 'Mine', 'project_id': 2},
                     {'project_name': 'Mine', 'user_id': 2},
                     {'project_name': 'Mine', 'confirmed': True},
                     {'project_name': ''}, {'project_name': []}]:
            with patch.object(planner, 'execute_jarvis_tool') as execute:
                self.assertFalse(self.context('tasks.list', args)['ok'])
                execute.assert_not_called()
        self.assertEqual(self.context('tasks.list', {'project_id': 2})['error']['code'], 'not_found')

    def test_id_based_calls_unchanged_and_no_discovery(self):
        with patch.object(planner, 'execute_jarvis_tool', wraps=planner.execute_jarvis_tool) as execute:
            self.assertTrue(self.context('tasks.list', {'project_id': 1})['ok'])
            self.assertEqual([c.args[1] for c in execute.call_args_list], ['tasks.list'])

    def test_planner_proposes_named_final_action_in_one_call(self):
        decision = {'action': 'tool', 'tool': 'tasks.create',
                    'arguments': {'project_name': 'Mine', 'title': 'Essay'}}
        response = {'reply': json.dumps(decision), 'provider': 'test', 'model': 'test',
                    'usage': {'input_tokens': 10, 'output_tokens': 5}}
        with patch.object(planner, '_routed_completion', return_value=response) as ai:
            recorder = Mock()
            planned = planner.plan_jarvis_action([], 'Add Essay to Mine', record_usage=recorder)
            self.assertEqual(planned, decision)
            self.assertEqual(self.context(planned['tool'], planned['arguments'])['error']['code'], 'confirmation_required')
            ai.assert_called_once()
            recorder.assert_called_once_with('test', 'test', 10, 5)

    def test_planning_schema_does_not_change_executable_schema(self):
        definitions = {d['name']: d for d in planner.get_jarvis_planning_definitions()}
        self.assertEqual(len(definitions['tasks.list']['parameters']['oneOf']), 2)
        self.assertFalse(planner.validate_jarvis_tool_call({
            'name': 'tasks.list', 'arguments': {'project_name': 'Mine'}})['ok'])
        self.assertFalse(planner.validate_jarvis_proposal('markets.quote', {'project_name': 'Mine'})['ok'])


if __name__ == '__main__':
    unittest.main()

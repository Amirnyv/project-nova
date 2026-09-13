"""Phase 2 regression tests; provider calls and application storage are isolated."""
import json
import unittest
from unittest.mock import Mock, patch, call

from services import jarvis_planner as planner
import test_jarvis_tools
import test_launch_hardening


class PlannerTests(unittest.TestCase):
    def plan(self, reply, recorder=None):
        self.recorder = recorder or Mock()
        response = {'reply': reply, 'provider': 'test', 'model': 'planner',
                    'usage': {'input_tokens': 12, 'output_tokens': 3}}
        with patch.object(planner, '_routed_completion', return_value=response) as ai:
            result = planner.plan_jarvis_action(
                [{'role': 'user', 'content': 'Show my projects'}],
                'Show my projects', record_usage=self.recorder)
            self.assertEqual(ai.call_args.kwargs['max_tokens'], 256)
            self.assertEqual(ai.call_args.kwargs['temperature'], 0)
        return result

    def test_normal_response_and_accounting(self):
        self.assertEqual(self.plan('{"action":"respond"}'), {'action': 'respond'})
        self.recorder.assert_called_once_with('test', 'planner', 12, 3)

    def test_valid_read_and_write_decisions(self):
        for name, args in [('projects.list', {}), ('tasks.create', {'project_id': 1, 'title': 'Essay'})]:
            decision = {'action': 'tool', 'tool': name, 'arguments': args}
            self.assertEqual(self.plan(json.dumps(decision)), decision)

    def test_invalid_outputs_fall_back_and_still_account(self):
        for output in ['not JSON', '[]', 'null', '"text"', '{',
                       '{"action":"tool","tool":"shell.run","arguments":{}}',
                       '{"action":"tool","tool":"projects.list","arguments":{"user_id":2}}',
                       '{"action":"tool","tool":"projects.list","arguments":{},"confirmed":true}']:
            self.assertEqual(self.plan(output), {'action': 'respond'})
            self.recorder.assert_called_once()

    def test_provider_failure_falls_back_without_invented_usage(self):
        recorder = Mock()
        with patch.object(planner, '_routed_completion', side_effect=RuntimeError('private')):
            self.assertEqual(planner.plan_jarvis_action([], 'Hi', record_usage=recorder), {'action': 'respond'})
        recorder.assert_not_called()

    def test_accounting_failure_is_not_swallowed(self):
        with self.assertRaises(RuntimeError):
            self.plan('{"action":"respond"}', Mock(side_effect=RuntimeError('db failed')))


class ToolContextTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_jarvis_tools.JarvisToolsTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def context(self, name, args):
        return planner.jarvis_result_context(1, {'action': 'tool', 'tool': name, 'arguments': args})

    def test_read_executes_for_server_user(self):
        context = self.context('projects.list', {})
        self.assertIn('Mine', context[-1]['content'])
        self.assertNotIn('Theirs', context[-1]['content'])
        self.assertIn('untrusted data', context[0]['content'])

    def test_cross_user_and_identity_injection_rejected(self):
        self.assertIn('not_found', self.context('projects.get', {'project_id': 2})[-1]['content'])
        self.assertIn('invalid_arguments', self.context('projects.list', {'user_id': 2})[-1]['content'])

    def test_write_returns_confirmation_without_mutation(self):
        before = self.fixture.query('SELECT * FROM project_tasks')
        for name, args in [('tasks.create', {'project_id': 1, 'title': 'Essay'}),
                           ('tasks.toggle', {'project_id': 1, 'task_id': 1, 'completed': True})]:
            self.assertIn('confirmation_required', self.context(name, args)[-1]['content'])
        self.assertEqual(before, self.fixture.query('SELECT * FROM project_tasks'))


class ChatIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_launch_hardening.HardeningTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.ns = self.fixture.ns

    def test_tool_context_stream_and_separate_usage(self):
        decision = {'action': 'tool', 'tool': 'projects.list', 'arguments': {}}
        def plan(messages, user_message, *, record_usage):
            record_usage('test', 'planner', 12, 3)
            return decision
        self.ns['plan_jarvis_action'].side_effect = plan
        context = [{'role': 'user', 'content': 'Internal safe tool result'}]
        self.ns['jarvis_result_context'].return_value = context
        response = self.fixture.chat(message='Show me my projects')
        events = [json.loads(line) for line in response.text.splitlines()]
        self.assertEqual([e['type'] for e in events], ['delta', 'done'])
        self.assertEqual(events[0]['delta'], 'Hello')
        self.assertEqual(events[-1]['conversation_id'], 1)
        self.ns['jarvis_result_context'].assert_called_once_with(1, decision)
        self.assertEqual(self.fixture.router.call_args.args[0][-1], context[0])
        self.assertEqual(self.ns['record_ai_usage'].call_args_list,
                         [call(1, 1, 'test:planner', 12, 3), call(1, 1, 'test:test-model', 120, 30)])
        self.assertTrue(any(c.args[2] == 'assistant' for c in self.ns['save_conversation_message'].call_args_list))

    def test_planning_exhausts_allowance_before_tool_and_final_call(self):
        self.ns['check_ai_usage_limit'].side_effect = [{'allowed': True}, {'allowed': False}]
        response = self.fixture.chat()
        self.assertIn('"type": "error"', response.text)
        self.fixture.router.assert_not_called()
        self.ns['jarvis_result_context'].assert_not_called()

    def test_web_search_skips_planner_and_router(self):
        response = self.fixture.chat(message='Search the web for current news')
        self.assertIn('"type": "done"', response.text)
        self.ns['plan_jarvis_action'].assert_not_called()
        self.fixture.router.assert_not_called()
        self.assertEqual(self.fixture.provider.responses.create.call_args.kwargs['tools'][0]['type'], 'web_search')
        self.ns['record_ai_usage'].assert_called_once_with(1, 1, 'gpt-5-mini', 120, 30)

    def test_broken_routed_stream_preserves_partial_content_and_closes(self):
        stream = test_launch_hardening.FakeStream([
            {'type': 'start', 'provider': 'test', 'model': 'test-model'},
            {'type': 'delta', 'delta': 'Partial'}, RuntimeError('synthetic failure'),
        ])
        self.fixture.router.return_value = stream
        response = self.fixture.chat()
        events = [json.loads(line) for line in response.text.splitlines()]
        self.assertEqual([e['type'] for e in events], ['delta', 'error'])
        self.assertNotIn('synthetic failure', response.text)
        self.assertTrue(stream.closed)
        self.ns['record_ai_usage'].assert_called_once_with(1, 1, 'test:test-model', 0, 0)
        self.ns['save_conversation_message'].assert_any_call(1, 1, 'assistant', 'Partial', output_tokens=0)

    def test_access_denial_skips_planner(self):
        self.ns['check_ai_usage_limit'].return_value = {'allowed': False, 'reason': 'usage_limit_reached'}
        self.assertEqual(self.fixture.chat().status_code, 429)
        self.ns['plan_jarvis_action'].assert_not_called()

    def test_disconnect_records_planner_and_final_once(self):
        def plan(messages, user_message, *, record_usage):
            record_usage('test', 'planner', 12, 3)
            return {'action': 'respond'}
        self.ns['plan_jarvis_action'].side_effect = plan
        response = self.fixture.chat(buffered=False)
        self.ns['record_ai_usage'].assert_called_once_with(1, 1, 'test:planner', 12, 3)
        response.close()
        self.assertEqual(self.ns['record_ai_usage'].call_count, 2)
        self.assertTrue(self.fixture.router_stream.closed)


if __name__ == '__main__':
    unittest.main()

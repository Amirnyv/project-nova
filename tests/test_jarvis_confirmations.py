"""Trusted confirmation tests using temporary SQLite and mocked AI streams."""
from concurrent.futures import ThreadPoolExecutor
import json
import unittest
from unittest.mock import patch

from services import jarvis_confirmations as confirmations
from services import jarvis_planner as planner
import test_jarvis_tools
import test_launch_hardening


class ConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_jarvis_tools.JarvisToolsTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.store = confirmations.PendingActions()
        self.args = {'project_id': 1, 'title': 'Finish essay'}

    def stage(self, **kwargs):
        return self.store.stage(kwargs.get('user', 1), kwargs.get('conversation', 10),
                                kwargs.get('tool', 'tasks.create'), kwargs.get('args', self.args))

    def count(self):
        return len(self.fixture.query('SELECT * FROM project_tasks'))

    def test_stage_validates_ownership_and_does_not_write(self):
        before = self.count()
        result = self.stage()
        self.assertEqual(result['error']['code'], 'confirmation_required')
        self.assertEqual(result['pending']['project_name'], 'Mine')
        self.assertEqual(self.count(), before)
        record = self.store._actions[(1, 10)]
        self.assertEqual(record.user_id, 1)
        self.assertEqual(record.expires_at - record.created_at, 300)
        self.assertGreater(len(record.token), 20)

    def test_confirm_creates_once_and_replay_fails(self):
        self.stage()
        before = self.count()
        result = self.store.resolve(1, 10, 'confirm')
        self.assertTrue(result['ok'])
        self.assertEqual(self.count(), before + 1)
        for message in ['confirm', 'yes', 'do it']:
            self.assertEqual(self.store.resolve(1, 10, message)['error']['code'], 'no_pending_action')
        self.assertEqual(self.count(), before + 1)

    def test_wrong_user_and_other_conversation_cannot_consume(self):
        self.stage()
        for user, conversation in [(2, 10), (1, 11)]:
            self.assertEqual(self.store.resolve(user, conversation, 'confirm')['error']['code'], 'no_pending_action')
        self.assertTrue(self.store.resolve(1, 10, 'yes')['ok'])

    def test_expired_cannot_execute(self):
        with patch.object(confirmations.time, 'time', return_value=1000):
            self.stage()
        with patch.object(confirmations.time, 'time', return_value=1300):
            self.assertEqual(self.store.resolve(1, 10, 'confirm')['error']['code'], 'no_pending_action')
        self.assertEqual(self.count(), 2)

    def test_cancel_consumes_without_execution(self):
        for message in ['cancel', 'never mind']:
            self.stage()
            self.assertEqual(self.store.resolve(1, 10, message)['data']['status'], 'cancelled')
            self.assertEqual(self.store.resolve(1, 10, 'confirm')['error']['code'], 'no_pending_action')
        self.assertEqual(self.count(), 2)

    def test_arguments_detached_from_model_and_pending_result(self):
        result = self.stage()
        self.args['title'] = 'Changed by model'
        result['pending']['arguments']['title'] = 'Changed by client'
        executed = self.store.resolve(1, 10, 'do it')
        self.assertEqual(executed['data']['title'], 'Finish essay')

    def test_no_authority_from_model_arguments(self):
        for args in [dict(self.args, user_id=2), dict(self.args, confirmed=True),
                     dict(self.args, title=[]), {}]:
            self.assertEqual(self.stage(args=args)['error']['code'], 'invalid_arguments')
        for uid in [True, '1', None]:
            self.assertEqual(self.stage(user=uid)['error']['code'], 'invalid_context')
        self.assertEqual(self.store._actions, {})

    def test_ownership_required_before_proposal_and_at_execution(self):
        self.assertEqual(self.stage(args={'project_id': 2, 'title': 'No'})['error']['code'], 'not_found')
        self.stage()
        db = self.fixture.connect()
        db.execute('UPDATE projects SET user_id=2 WHERE id=1')
        db.commit()
        db.close()
        self.assertEqual(self.store.resolve(1, 10, 'confirm')['error']['code'], 'not_found')
        self.assertEqual(self.count(), 2)

    def test_toggle_runs_exactly_once(self):
        args = {'project_id': 1, 'task_id': 1, 'completed': True}
        self.stage(tool='tasks.toggle', args=args)
        with patch.object(confirmations, 'execute_jarvis_tool', wraps=confirmations.execute_jarvis_tool) as dispatcher:
            self.assertTrue(self.store.resolve(1, 10, 'confirm')['ok'])
            self.assertFalse(self.store.resolve(1, 10, 'confirm')['ok'])
            dispatcher.assert_called_once_with(1, 'tasks.toggle', args, confirmed=True)
        self.assertEqual(self.fixture.query('SELECT completed FROM project_tasks WHERE id=1')[0]['completed'], 1)

    def test_cross_user_task_cannot_be_proposed(self):
        result = self.stage(tool='tasks.toggle', args={'project_id': 1, 'task_id': 2, 'completed': True})
        self.assertEqual(result['error']['code'], 'not_found')
        self.assertEqual(self.store._actions, {})

    def test_malformed_confirmation_does_not_execute(self):
        self.stage()
        for message in [None, {}, 'confirm with title hacked', 'yes and delete everything', '']:
            self.assertEqual(self.store.resolve(1, 10, message)['error']['code'], 'invalid_confirmation')
        self.assertEqual(self.count(), 2)
        self.assertTrue(self.store.resolve(1, 10, ' CONFIRM ')['ok'])

    def test_only_two_whitelisted_writes(self):
        for tool in ['projects.delete', 'shell.run', 'trades.buy', 'projects.list', []]:
            self.assertEqual(self.stage(tool=tool)['error']['code'], 'unsupported_action')
        self.assertEqual(confirmations.WRITE_TOOLS, {'tasks.create', 'tasks.toggle'})

    def test_concurrent_confirms_execute_only_once(self):
        self.stage()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.store.resolve(1, 10, 'confirm'), range(4)))
        self.assertEqual(sum(r['ok'] for r in results), 1)
        self.assertEqual(self.count(), 3)

    def test_pending_cannot_be_silently_replaced(self):
        self.stage()
        self.assertEqual(self.stage(args=dict(self.args, title='Replacement'))['error']['code'], 'pending_exists')
        self.assertEqual(self.store.resolve(1, 10, 'confirm')['data']['title'], 'Finish essay')

    def test_discard_and_restart_fail_closed(self):
        self.stage()
        self.store.discard(1, 10)
        self.assertFalse(self.store.resolve(1, 10, 'confirm')['ok'])
        self.stage()
        restarted = confirmations.PendingActions()
        self.assertFalse(restarted.resolve(1, 10, 'confirm')['ok'])

    def test_capacity_is_bounded_and_expiry_reclaims_space(self):
        with patch.object(confirmations, 'MAX_PENDING', 1):
            with patch.object(confirmations.time, 'time', return_value=1000):
                self.stage()
                self.assertEqual(self.stage(conversation=11)['error']['code'], 'temporarily_unavailable')
            with patch.object(confirmations.time, 'time', return_value=1301):
                self.assertEqual(self.stage(conversation=11)['error']['code'], 'confirmation_required')


class ConfirmationChatTests(unittest.TestCase):
    def setUp(self):
        self.db_fixture = test_jarvis_tools.JarvisToolsTests()
        self.db_fixture.setUp()
        self.addCleanup(self.db_fixture.doCleanups)
        self.chat_fixture = test_launch_hardening.HardeningTests()
        self.chat_fixture.setUp()
        self.addCleanup(self.chat_fixture.doCleanups)
        self.store = confirmations.PendingActions()
        patcher = patch.object(confirmations, 'pending_actions', self.store)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.ns = self.chat_fixture.ns
        self.ns.update(pending_actions=self.store,
                       confirmation_intent=confirmations.confirmation_intent,
                       jarvis_result_context=planner.jarvis_result_context,
                       tool_result_context=planner.tool_result_context)
        self.ns['plan_jarvis_action'].return_value = {
            'action': 'tool', 'tool': 'tasks.create',
            'arguments': {'project_id': 1, 'title': 'Finish essay'}}

    def chat(self, message, **kwargs):
        self.chat_fixture.router.return_value = test_launch_hardening.FakeStream([
            {'type': 'start', 'provider': 'test', 'model': 'test-model'},
            {'type': 'delta', 'delta': 'Mocked Nova answer'},
            {'type': 'done', 'provider': 'test', 'model': 'test-model',
             'usage': {'input_tokens': 120, 'output_tokens': 30}},
        ])
        response = self.chat_fixture.chat(message=message, **kwargs)
        self.assertEqual(response.status_code, 200)
        events = [json.loads(line) for line in response.text.splitlines()]
        self.assertEqual([event['type'] for event in events], ['delta', 'done'])
        self.assertEqual(events[-1]['conversation_id'], 1)
        return self.chat_fixture.router.call_args.args[0][-1]['content']

    def test_propose_confirm_replay_and_model_cannot_change_action(self):
        self.assertIn('confirmation_required', self.chat('Add finish essay to project 1'))
        self.assertEqual(len(self.db_fixture.query('SELECT * FROM project_tasks')), 2)
        self.ns['plan_jarvis_action'].reset_mock()
        self.ns['plan_jarvis_action'].side_effect = AssertionError('Planner must not run on confirmation')
        content = self.chat('confirm', arguments={'title': 'Hacked'}, user_id=2, confirmed=True)
        self.assertIn('Finish essay', content)
        self.assertNotIn('Hacked', content)
        self.assertEqual(len(self.db_fixture.query('SELECT * FROM project_tasks')), 3)
        self.assertIn('no_pending_action', self.chat('confirm'))
        self.assertEqual(len(self.db_fixture.query('SELECT * FROM project_tasks')), 3)
        self.ns['plan_jarvis_action'].assert_not_called()

    def test_cancel_and_other_user(self):
        self.chat('Add a task')
        other = self.chat_fixture.new_client('2')
        self.assertIn('no_pending_action', self.chat('confirm', web=other))
        self.assertIn('cancelled', self.chat('cancel'))
        self.assertIn('no_pending_action', self.chat('yes'))
        self.assertEqual(len(self.db_fixture.query('SELECT * FROM project_tasks')), 2)

    def test_different_message_discards_old_action(self):
        self.chat('Add a task')
        self.ns['plan_jarvis_action'].return_value = {'action': 'respond'}
        self.chat('Hello Nova')
        self.assertIn('no_pending_action', self.chat('yes'))
        self.assertEqual(len(self.db_fixture.query('SELECT * FROM project_tasks')), 2)

    def test_read_tools_still_work(self):
        self.ns['plan_jarvis_action'].return_value = {'action': 'tool', 'tool': 'projects.list', 'arguments': {}}
        content = self.chat('Show my projects')
        self.assertIn('Mine', content)
        self.assertNotIn('Theirs', content)
        self.assertEqual(self.store._actions, {})

    def test_confirmation_in_web_enabled_custom_agent_does_not_plan_or_search(self):
        self.chat('Add a task')
        self.ns['plan_jarvis_action'].reset_mock()
        self.chat('confirm', custom_agent={'name': 'Test', 'instructions': 'Help', 'web_search': True})
        self.ns['plan_jarvis_action'].assert_not_called()
        self.chat_fixture.provider.responses.create.assert_not_called()
        self.assertEqual(len(self.db_fixture.query('SELECT * FROM project_tasks')), 3)

    def test_usage_denial_does_not_execute_pending_action(self):
        self.chat('Add a task')
        self.ns['check_ai_usage_limit'].return_value = {'allowed': False, 'reason': 'usage_limit_reached'}
        response = self.chat_fixture.chat(message='confirm')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(len(self.db_fixture.query('SELECT * FROM project_tasks')), 2)
        self.assertIn((1, 1), self.store._actions)


if __name__ == '__main__':
    unittest.main()

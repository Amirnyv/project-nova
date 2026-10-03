"""Single-process development confirmation store; no database or provider imports.

Pending actions live for five minutes, scoped to server user/conversation IDs.
Restarting loses them. Multiple workers do NOT share this store: deploy with one
worker until an approved shared, atomic store exists. Consuming before dispatch
prevents retries/replays, but a crash can lose an action or its success response.
Never retry a consumed write automatically. No tokens or private arguments logged.
"""
from dataclasses import dataclass
import json
import secrets
from threading import Lock
import time

from services.jarvis_tools import execute_jarvis_tool, validate_jarvis_tool_arguments

WRITE_TOOLS = frozenset({'tasks.create', 'tasks.toggle'})
TTL_SECONDS = 300
MAX_PENDING = 10000


def confirmation_intent(message):
    if not isinstance(message, str):
        return None
    text = message.strip().casefold()
    if text in {'yes', 'confirm', 'do it'}:
        return 'confirm'
    if text in {'cancel', 'never mind'}:
        return 'cancel'
    return None


def _error(code, message, tool=None):
    return {'ok': False, 'tool': tool, 'error': {'code': code, 'message': message}}


def _valid_context(user_id, conversation_id):
    return all(type(value) is int and 1 <= value <= 2147483647
               for value in (user_id, conversation_id))


@dataclass(frozen=True)
class PendingAction:
    user_id: int
    conversation_id: int
    tool_name: str
    arguments_json: str
    created_at: float
    expires_at: float
    token: str


class PendingActions:
    def __init__(self):
        self._actions = {}
        self._lock = Lock()

    def discard(self, user_id, conversation_id):
        if _valid_context(user_id, conversation_id):
            with self._lock:
                self._actions.pop((user_id, conversation_id), None)

    def stage(self, user_id, conversation_id, tool_name, arguments):
        if not _valid_context(user_id, conversation_id):
            return _error('invalid_context', 'A valid authenticated conversation is required.')
        if not isinstance(tool_name, str) or tool_name not in WRITE_TOOLS:
            return _error('unsupported_action', 'That action cannot be confirmed.')
        validated = validate_jarvis_tool_arguments(tool_name, arguments)
        if not validated['ok']:
            return validated
        args = validated['data']
        # Check ownership before offering the action, and again in the dispatcher
        # on confirmation. Never grant authority just because an ID was planned.
        project = execute_jarvis_tool(user_id, 'projects.get', {'project_id': args['project_id']})
        if not project['ok']:
            return project
        if tool_name == 'tasks.toggle':
            tasks = execute_jarvis_tool(user_id, 'tasks.list', {'project_id': args['project_id']})
            if not tasks['ok']:
                return tasks
            if not any(task['id'] == args['task_id'] for task in tasks['data']):
                return _error('not_found', 'The requested item was not found.', tool_name)
        now = time.time()
        pending = PendingAction(user_id, conversation_id, tool_name,
                                json.dumps(args), now, now + TTL_SECONDS,
                                secrets.token_urlsafe(24))
        with self._lock:
            self._actions = {key: value for key, value in self._actions.items()
                             if value.expires_at > now}
            key = (user_id, conversation_id)
            if key in self._actions:
                return _error('pending_exists', 'Confirm or cancel the existing action first.')
            if len(self._actions) >= MAX_PENDING:
                return _error('temporarily_unavailable', 'Please try the action again later.')
            self._actions[key] = pending
        return {'ok': False, 'tool': tool_name, 'error': {
            'code': 'confirmation_required',
            'message': 'Action not performed. Reply confirm to approve or cancel to discard within five minutes.'},
            'pending': {'tool': tool_name, 'arguments': json.loads(pending.arguments_json),
                        'project_name': project['data']['name'], 'expires_at': pending.expires_at}}

    def resolve(self, user_id, conversation_id, message):
        intent = confirmation_intent(message)
        if intent is None:
            return _error('invalid_confirmation', 'Use confirm or cancel without changing the action.')
        if not _valid_context(user_id, conversation_id):
            return _error('invalid_context', 'A valid authenticated conversation is required.')
        # Atomic removal: only one thread/request can acquire execution authority.
        with self._lock:
            pending = self._actions.pop((user_id, conversation_id), None)
        if pending is None or pending.expires_at <= time.time():
            return _error('no_pending_action', 'No valid pending action exists in this conversation. Nothing was executed.')
        if intent == 'cancel':
            return {'ok': True, 'tool': pending.tool_name, 'data': {
                'status': 'cancelled', 'message': 'Action cancelled. Nothing was executed.'}}
        # Recheck whitelist and validation; the model supplies none of these values.
        if pending.tool_name not in WRITE_TOOLS:
            return _error('unsupported_action', 'That action cannot be confirmed.')
        return execute_jarvis_tool(pending.user_id, pending.tool_name,
                                  json.loads(pending.arguments_json), confirmed=True)


pending_actions = PendingActions()

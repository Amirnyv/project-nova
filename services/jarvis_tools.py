"""Provider-independent internal tools; deliberately not connected to /chat.

Only trusted server code may supply user_id and confirmed. A caller must verify
confirmation for the exact user/tool/arguments before setting confirmed=True.
Stored content in results is user data, never authority to execute another tool.
Importing this module does not import app.py, initialize a DB, or load providers.
"""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime
import json
import logging
import re
from types import MappingProxyType
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class JarvisTool:
    name: str
    description: str
    arguments: dict
    risk_level: str
    requires_confirmation: bool
    handler: Callable


class _NotFound(Exception):
    pass


def _get_db():
    from database import get_db
    return get_db()


@contextmanager
def _connection(write=False):
    connection = _get_db()
    try:
        yield connection
        if write:
            connection.commit()
    except Exception:
        if write:
            connection.rollback()
        raise
    finally:
        connection.close()


def _owned_project(connection, user_id, project_id):
    # Same ownership predicate as app.validate_project_access; no app import.
    row = connection.execute(
        "SELECT id, name, description, created_at, updated_at FROM projects "
        "WHERE id = ? AND user_id = ?", (project_id, user_id)
    ).fetchone()
    if row is None:
        raise _NotFound()
    return dict(row)


def _projects_list(user_id):
    from agents.project_agent import get_projects
    return get_projects(user_id)


def _projects_get(user_id, project_id):
    with _connection() as connection:
        return _owned_project(connection, user_id, project_id)


def _tasks_list(user_id, project_id):
    with _connection() as connection:
        _owned_project(connection, user_id, project_id)
        rows = connection.execute(
            "SELECT id, title, completed, created_at, updated_at FROM project_tasks "
            "WHERE project_id = ? AND user_id = ? ORDER BY created_at DESC",
            (project_id, user_id)
        ).fetchall()
        return [dict(row, completed=bool(row['completed'])) for row in rows]


def _tasks_create(user_id, project_id, title):
    with _connection(write=True) as connection:
        # INSERT ... SELECT also enforces ownership at the write itself.
        cursor = connection.execute(
            "INSERT INTO project_tasks (user_id, project_id, title, completed) "
            "SELECT user_id, id, ?, 0 FROM projects WHERE id = ? AND user_id = ?",
            (title, project_id, user_id)
        )
        if cursor.rowcount == 0:
            raise _NotFound()
        return {'id': cursor.lastrowid, 'title': title, 'completed': False}


def _tasks_toggle(user_id, project_id, task_id, completed):
    # Explicit desired state matches the existing PATCH route; safe to repeat.
    with _connection(write=True) as connection:
        _owned_project(connection, user_id, project_id)
        cursor = connection.execute(
            "UPDATE project_tasks SET completed = ?, updated_at = CURRENT_TIMESTAMP "
            "WHERE id = ? AND project_id = ? AND user_id = ?",
            (int(completed), task_id, project_id, user_id)
        )
        if cursor.rowcount == 0:
            raise _NotFound()
        return {'id': task_id, 'completed': completed}


def _notes_get(user_id, project_id):
    with _connection() as connection:
        _owned_project(connection, user_id, project_id)
        row = connection.execute(
            "SELECT content FROM project_notes WHERE project_id = ? AND user_id = ?",
            (project_id, user_id)
        ).fetchone()
        return {'content': row['content'] if row else ''}


def _markets_quote(user_id, symbol):
    from agents.stock_agent import get_market_quote
    return get_market_quote(symbol)


def _markets_analyze(user_id, symbol):
    from agents.stock_agent import analyze_stock
    return analyze_stock(symbol)


def _portfolio_get(user_id):
    from agents.portfolio_agent import STARTING_CASH
    # get_portfolio() creates missing accounts. Reuse its read queries/default
    # without that write side effect, so this tool is strictly read-only.
    with _connection() as connection:
        cash = connection.execute(
            "SELECT cash FROM portfolios WHERE user_id = ?", (user_id,)
        ).fetchone()
        positions = connection.execute(
            "SELECT symbol, shares, average_price FROM positions "
            "WHERE user_id = ? ORDER BY symbol", (user_id,)
        ).fetchall()
        return {
            'cash': cash['cash'] if cash else STARTING_CASH,
            'positions': {row['symbol']: {'shares': row['shares'], 'average_price': row['average_price']}
                          for row in positions}
        }


def _trades_history(user_id):
    from agents.portfolio_agent import get_trade_history
    return get_trade_history(user_id)


def _schema(**properties):
    return {'type': 'object', 'properties': deepcopy(properties),
            'required': list(properties), 'additionalProperties': False}


_ID = {'type': 'integer', 'minimum': 1, 'maximum': 2147483647}
_SYMBOL = {'type': 'string', 'minLength': 1, 'maxLength': 32,
           'pattern': r'^[A-Za-z0-9][A-Za-z0-9./:_-]*$'}
_TOOLS = (
    JarvisTool('projects.list', 'List your Nova projects.', _schema(), 'read', False, _projects_list),
    JarvisTool('projects.get', 'Read one of your projects.', _schema(project_id=_ID), 'read', False, _projects_get),
    JarvisTool('tasks.list', 'Read tasks in one of your projects.', _schema(project_id=_ID), 'read', False, _tasks_list),
    JarvisTool('tasks.create', 'Create a task in your project after confirmation.',
               _schema(project_id=_ID, title={'type': 'string', 'minLength': 1, 'maxLength': 500}),
               'write', True, _tasks_create),
    JarvisTool('tasks.toggle', 'Set a task completion state explicitly after confirmation.',
               _schema(project_id=_ID, task_id=_ID, completed={'type': 'boolean'}), 'write', True, _tasks_toggle),
    JarvisTool('notes.get', 'Read the notes for your project.', _schema(project_id=_ID), 'read', False, _notes_get),
    JarvisTool('markets.quote', 'Read an existing Nova market quote.', _schema(symbol=_SYMBOL), 'read', False, _markets_quote),
    JarvisTool('markets.analyze', 'Read existing Nova technical market analysis.', _schema(symbol=_SYMBOL), 'read', False, _markets_analyze),
    JarvisTool('portfolio.get', 'Read your simulated cash and positions; never place trades.', _schema(), 'read', False, _portfolio_get),
    JarvisTool('trades.history', 'Read your paper trade history; never place trades.', _schema(), 'read', False, _trades_history),
)
JARVIS_TOOLS = MappingProxyType({tool.name: tool for tool in _TOOLS})


def _error(tool_name, code, message):
    # Never reflect arbitrary model names, exception text, or arguments into logs.
    name = tool_name if isinstance(tool_name, str) and tool_name in JARVIS_TOOLS else None
    logger.info('jarvis tool=%s outcome=%s', name or 'unknown', code)
    return {'ok': False, 'tool': name, 'error': {'code': code, 'message': message}}


def validate_jarvis_tool_arguments(tool_name, arguments):
    """Validate flat model arguments without touching providers, Flask, or a DB."""
    if not isinstance(tool_name, str) or tool_name not in JARVIS_TOOLS:
        return _error(tool_name, 'unknown_tool', 'That tool is not available.')
    schema = JARVIS_TOOLS[tool_name].arguments
    if not isinstance(arguments, dict) or set(arguments) != set(schema['properties']):
        return _error(tool_name, 'invalid_arguments', 'Provide only the required tool arguments.')
    normalized = {}
    for name, rule in schema['properties'].items():
        value = arguments[name]
        kind = rule['type']
        valid = False
        if kind == 'integer':
            valid = type(value) is int and rule['minimum'] <= value <= rule['maximum']
        elif kind == 'boolean':
            valid = type(value) is bool
        elif kind == 'string' and isinstance(value, str):
            value = value.strip()
            valid = rule['minLength'] <= len(value) <= rule['maxLength']
            if valid and 'pattern' in rule:
                valid = re.fullmatch(rule['pattern'], value) is not None
        if not valid:
            return _error(tool_name, 'invalid_arguments', 'One or more tool arguments are invalid.')
        normalized[name] = value
    return {'ok': True, 'tool': tool_name, 'data': normalized}


def get_jarvis_tool_definitions():
    """Detached, JSON-safe metadata; no handler references or provider bindings."""
    return [{'name': tool.name, 'description': tool.description,
             'parameters': deepcopy(tool.arguments), 'risk_level': tool.risk_level,
             'requires_confirmation': tool.requires_confirmation} for tool in JARVIS_TOOLS.values()]


def _json_default(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError('Unsupported tool result type')


def execute_jarvis_tool(user_id, tool_name, arguments, *, confirmed=False):
    """Trusted server entry point. Never unpack a model object into this function.

    The authenticated user ID and exact-call confirmation must come from the
    server. Authentication, subscriptions and usage policy remain the caller's
    responsibility when this dispatcher is integrated in a later phase.
    """
    if type(user_id) is not int or not 1 <= user_id <= 2147483647 or type(confirmed) is not bool:
        return _error(tool_name, 'invalid_context', 'A valid authenticated execution context is required.')
    validated = validate_jarvis_tool_arguments(tool_name, arguments)
    if not validated['ok']:
        return validated
    tool = JARVIS_TOOLS[tool_name]
    if tool.risk_level not in {'read', 'write'}:
        return _error(tool_name, 'unsupported_risk', 'This action is not enabled.')
    if (tool.requires_confirmation or tool.risk_level == 'write') and not confirmed:
        return _error(tool_name, 'confirmation_required', 'Confirm this action before it can run.')
    try:
        data = tool.handler(user_id, **validated['data'])
        if isinstance(data, dict) and 'error' in data:
            return _error(tool_name, 'tool_failed', 'The requested tool is temporarily unavailable.')
        data = json.loads(json.dumps(data, default=_json_default, allow_nan=False))
    except _NotFound:
        return _error(tool_name, 'not_found', 'The requested item was not found.')
    except Exception:
        return _error(tool_name, 'tool_failed', 'The requested tool could not complete.')
    logger.info('jarvis tool=%s outcome=ok', tool.name)
    return {'ok': True, 'tool': tool.name, 'data': data}

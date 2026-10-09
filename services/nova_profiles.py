"""Private opt-in profiles; independent of account usernames and entitlements."""
import re
import sqlite3

RESERVED_HANDLES = frozenset({'nova', 'projectnova', 'project_nova', 'admin', 'administrator',
    'staff', 'support', 'system', 'moderator', 'official', 'security', 'help', 'root', 'jarvis',
    'workfield', 'workfieldhq', 'deleted', 'null', 'undefined'})
PUBLIC_COLUMNS = 'id, handle, display_name, discoverable, allow_group_invites, status, created_at, updated_at'


class ProfileError(ValueError):
    def __init__(self, code, message, status=400):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def canonicalize_handle(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_]{3,30}', value):
        raise ProfileError('invalid_handle', 'Use 3–30 ASCII letters, digits or underscores.')
    handle = value.lower()
    if handle in RESERVED_HANDLES or handle.startswith(('nova_', 'staff_', 'system_', 'admin_')):
        raise ProfileError('reserved_handle', 'This handle is reserved.')
    return handle


def serialize(row):
    if row is None:
        return None
    result = {key: row[key] for key in PUBLIC_COLUMNS.split(', ')}
    result['id'] = str(result['id'])
    for key in ('discoverable', 'allow_group_invites'):
        result[key] = bool(result[key])
    for key in ('created_at', 'updated_at'):
        result[key] = str(result[key])
    return result


def get_profile(get_db, user_id):
    db = get_db()
    try:
        return serialize(db.execute(f'SELECT {PUBLIC_COLUMNS} FROM nova_profiles WHERE user_id=?', (user_id,)).fetchone())
    finally:
        db.close()


def handle_available(get_db, value):
    handle = canonicalize_handle(value)
    db = get_db()
    try:
        available = db.execute('SELECT id FROM nova_profiles WHERE handle=?', (handle,)).fetchone() is None
        return {'handle': handle, 'available': available}
    finally:
        db.close()


def update_profile(get_db, user_id, fields, postgres=False):
    allowed = {'handle', 'display_name', 'discoverable', 'allow_group_invites'}
    if not isinstance(fields, dict) or not fields or set(fields) - allowed:
        raise ProfileError('invalid_fields', 'Provide only editable profile fields.')
    values = dict(fields)
    if 'handle' in values:
        values['handle'] = canonicalize_handle(values['handle'])
    if 'display_name' in values:
        name = values['display_name']
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80 or any(ord(c) < 32 for c in name):
            raise ProfileError('invalid_display_name', 'Display name must contain 1–80 characters without control characters.')
        values['display_name'] = name.strip()
    for key in ('discoverable', 'allow_group_invites'):
        if key in values:
            if type(values[key]) is not bool:
                raise ProfileError('invalid_fields', 'Privacy settings must be booleans.')
            values[key] = int(values[key])
    db = get_db()
    try:
        if not postgres:
            db.execute('BEGIN IMMEDIATE')
        # Lock the existing account even before a profile exists, avoiding create/update races.
        owner = db.execute('SELECT id FROM users WHERE id=?' + (' FOR UPDATE' if postgres else ''), (user_id,)).fetchone()
        if not owner:
            raise ProfileError('unauthorized', 'Sign in again.', 401)
        existing = db.execute('SELECT id, status FROM nova_profiles WHERE user_id=?', (user_id,)).fetchone()
        if existing:
            if existing['status'] != 'active':
                raise ProfileError('profile_unavailable', 'This profile cannot be updated.', 403)
            columns = ', '.join(key + '=?' for key in values)
            db.execute(f'UPDATE nova_profiles SET {columns}, updated_at=CURRENT_TIMESTAMP WHERE user_id=?', (*values.values(), user_id))
        else:
            if 'handle' not in values:
                raise ProfileError('handle_required', 'Choose a handle to create your profile.')
            values.setdefault('display_name', values['handle'])
            columns = ', '.join(values)
            placeholders = ', '.join('?' for _ in values)
            db.execute(f'INSERT INTO nova_profiles(user_id, {columns}) VALUES(?, {placeholders})', (user_id, *values.values()))
        result = serialize(db.execute(f'SELECT {PUBLIC_COLUMNS} FROM nova_profiles WHERE user_id=?', (user_id,)).fetchone())
        db.commit()
        return result
    except sqlite3.IntegrityError:
        db.rollback()
        raise ProfileError('profile_conflict', 'That handle is unavailable. Please choose another.', 409) from None
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def claim_profile(get_db, user_id, handle, postgres=False, **fields):
    return update_profile(get_db, user_id, dict(fields, handle=handle), postgres)

"""Shared account creation; no app import, provider calls or configuration reads."""
import re
import sqlite3
from werkzeug.security import generate_password_hash


class RegistrationError(ValueError):
    def __init__(self, code, message, status=400):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def create_account(get_db, username, email, password, confirm_password):
    fields = (username, email, password, confirm_password)
    if not all(isinstance(value, str) for value in fields):
        raise RegistrationError('invalid_request', 'Registration fields must be strings.')
    username, email = username.strip(), email.strip().lower()
    if not username or not email or not password:
        raise RegistrationError('invalid_request', 'Username, email, and password are required.')
    if len(username) > 80 or len(email) > 254 or max(len(password), len(confirm_password)) > 256:
        raise RegistrationError('invalid_request', 'Username, email, or password is too long.')
    # Practical ASCII email syntax; delivery/ownership is not verified here.
    local, sep, domain = email.rpartition('@')
    labels = domain.split('.')
    if (not sep or not 1 <= len(local) <= 64
            or not re.fullmatch(r"[a-z0-9!#$%&'*+/=?^_`{|}~.-]+", local)
            or local.startswith('.') or local.endswith('.') or '..' in local
            or len(labels) < 2
            or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in labels)):
        raise RegistrationError('invalid_email', 'Enter a valid email address.')
    if password != confirm_password:
        raise RegistrationError('password_mismatch', 'Passwords do not match.')
    if len(password) < 8:
        raise RegistrationError('invalid_password', 'Password must be at least 8 characters.')
    password_hash = generate_password_hash(password)
    db = get_db()
    try:
        cursor = db.execute('INSERT INTO users(username,email,password_hash) VALUES(?,?,?)',
                            (username, email, password_hash))
        uid = cursor.lastrowid
        db.execute('INSERT INTO portfolios(user_id,cash) VALUES(?,?)', (uid, 10000.0))
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        raise RegistrationError('duplicate_account', 'That username or email is already registered.', 409) from None
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return {'id': uid, 'username': username, 'email': email}

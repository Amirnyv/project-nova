"""Encrypted OAuth credential storage for Nova Connections."""

import json
import os

from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv

from database import get_db


class ConnectionVaultError(Exception):
    """A credential vault operation failed."""


def _get_cipher():
    load_dotenv()

    key = os.getenv("NOVA_CONNECTIONS_ENCRYPTION_KEY")

    if not key:
        raise ConnectionVaultError(
            "NOVA_CONNECTIONS_ENCRYPTION_KEY is not configured."
        )

    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as error:
        raise ConnectionVaultError(
            "Nova's connections encryption key is invalid."
        ) from error


def _encrypt(credentials):
    if not isinstance(credentials, dict):
        raise ValueError("Credentials must be a dictionary.")

    plaintext = json.dumps(credentials).encode("utf-8")
    return _get_cipher().encrypt(plaintext).decode("utf-8")


def _decrypt(encrypted_credentials):
    try:
        plaintext = _get_cipher().decrypt(
            encrypted_credentials.encode("utf-8")
        )
        return json.loads(plaintext.decode("utf-8"))
    except (InvalidToken, ValueError, UnicodeDecodeError) as error:
        raise ConnectionVaultError(
            "Unable to decrypt connection credentials."
        ) from error


def save_credentials(user_id, connection_id, credentials):
    """Encrypt and upsert credentials for a connection owned by user."""

    encrypted = _encrypt(credentials)
    db = get_db()

    try:
        owner = db.execute(
            """
            SELECT id
            FROM connections
            WHERE id = ? AND user_id = ?
            """,
            (connection_id, user_id),
        ).fetchone()

        if owner is None:
            raise ConnectionVaultError(
                "Connection not found for this user."
            )

        db.execute(
            """
            INSERT INTO connection_credentials (
                connection_id,
                encrypted_credentials
            )
            VALUES (?, ?)
            ON CONFLICT(connection_id)
            DO UPDATE SET
                encrypted_credentials = excluded.encrypted_credentials,
                updated_at = CURRENT_TIMESTAMP
            """,
            (connection_id, encrypted),
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def load_credentials(user_id, connection_id):
    """Return decrypted credentials only for an owned connection."""

    db = get_db()

    try:
        row = db.execute(
            """
            SELECT cc.encrypted_credentials
            FROM connection_credentials AS cc
            JOIN connections AS c
                ON c.id = cc.connection_id
            WHERE c.id = ? AND c.user_id = ?
            """,
            (connection_id, user_id),
        ).fetchone()

        if row is None:
            return None

        return _decrypt(row["encrypted_credentials"])

    finally:
        db.close()


def delete_credentials(user_id, connection_id):
    """Delete credentials only for a connection owned by user."""

    db = get_db()

    try:
        result = db.execute(
            """
            DELETE FROM connection_credentials
            WHERE connection_id IN (
                SELECT id
                FROM connections
                WHERE id = ? AND user_id = ?
            )
            """,
            (connection_id, user_id),
        )

        db.commit()
        return result.rowcount > 0

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

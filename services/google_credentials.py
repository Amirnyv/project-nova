"""Load and automatically refresh Google credentials for Nova."""

import os
from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from database import get_db
from services.connection_vault import (
    load_credentials,
    save_credentials,
)


class GoogleConnectionError(Exception):
    """The user's Google connection is unavailable."""


def get_google_credentials(user_id, connection_id=None):
    """Return usable Google credentials for this Nova user."""

    db = get_db()
    try:
        if connection_id is None:
            row = db.execute(
                """
                SELECT id
                FROM connections
                WHERE user_id = ?
                  AND provider = ?
                  AND status = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (user_id, "google", "connected"),
            ).fetchone()
        else:
            if type(connection_id) is not int or connection_id < 1:
                raise GoogleConnectionError(
                    "Invalid Google connection."
                )

            row = db.execute(
                """
                SELECT id
                FROM connections
                WHERE id = ?
                  AND user_id = ?
                  AND provider = ?
                  AND status = ?
                """,
                (
                    connection_id,
                    user_id,
                    "google",
                    "connected",
                ),
            ).fetchone()
    finally:
        db.close()

    if not row:
        raise GoogleConnectionError(
            "Google account unavailable. Connect or reconnect your account."
        )

    connection_id = int(row["id"])

    stored = load_credentials(user_id, connection_id)

    if not stored:
        raise GoogleConnectionError(
            "Google credentials are missing. Reconnect Google."
        )

    credentials = Credentials(
        token=stored.get("access_token"),
        refresh_token=stored.get("refresh_token"),
        token_uri=stored.get(
            "token_uri",
            "https://oauth2.googleapis.com/token",
        ),
        client_id=os.getenv("GOOGLE_OAUTH_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"),
        scopes=stored.get("scopes"),
    )

    if stored.get("expiry"):
        credentials.expiry = datetime.fromisoformat(
            stored["expiry"]
        ).replace(tzinfo=None)

    if credentials.expired or not credentials.token:
        if not credentials.refresh_token:
            raise GoogleConnectionError(
                "Google authorization expired. Reconnect Google."
            )

        credentials.refresh(Request())

        updated = dict(stored)
        updated["access_token"] = credentials.token
        updated["refresh_token"] = (
            credentials.refresh_token
            or stored.get("refresh_token")
        )
        updated["expiry"] = (
            credentials.expiry.isoformat()
            if credentials.expiry
            else None
        )

        save_credentials(
            user_id,
            connection_id,
            updated,
        )

    return credentials

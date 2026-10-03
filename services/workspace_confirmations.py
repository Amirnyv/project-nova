
"""Persistent Workspace proposal and approval management.

This module does not execute Google API operations.
"""

import hashlib
import hmac
import json
import secrets
import time
import uuid
from datetime import datetime, timezone

from database import get_db


TTL_SECONDS = 300

WRITE_OPERATIONS = frozenset({
    "gmail.send",
    "gmail.reply",
    "calendar.create",
    "calendar.update",
    "calendar.delete",
})


class WorkspaceConfirmationError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _digest(value):
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def _canonical_json(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _valid_connection(db, user_id, connection_id):
    if (
        type(user_id) is not int
        or type(connection_id) is not int
        or user_id < 1
        or connection_id < 1
    ):
        return False

    row = db.execute(
        """
        SELECT id
        FROM connections
        WHERE id = ?
          AND user_id = ?
          AND provider = 'google'
          AND status = 'connected'
        """,
        (connection_id, user_id),
    ).fetchone()

    return row is not None


def stage_workspace_action(
    user_id,
    connection_id,
    operation,
    arguments,
    expected_version=None,
):
    """Store a proposal without executing it."""

    if operation not in WRITE_OPERATIONS:
        raise WorkspaceConfirmationError(
            "unsupported_action",
            "Unsupported Workspace operation.",
        )

    if not isinstance(arguments, dict):
        raise WorkspaceConfirmationError(
            "invalid_arguments",
            "Invalid action arguments.",
        )

    # Provider-specific validation and OAuth scope checks
    # must be performed by the preparation layer.
    arguments_json = _canonical_json(arguments)
    arguments_hash = _digest(arguments_json)

    proposal_id = str(uuid.uuid4())
    request_id = str(uuid.uuid4())
    confirmation_token = secrets.token_urlsafe(32)

    now = int(time.time())
    expires_at = now + TTL_SECONDS

    db = get_db()

    try:
        if not _valid_connection(
            db, user_id, connection_id
        ):
            raise WorkspaceConfirmationError(
                "permission_denied",
                "Google account unavailable.",
            )

        db.execute(
            """
            INSERT INTO workspace_proposals (
                proposal_id,
                user_id,
                connection_id,
                operation,
                arguments_json,
                arguments_hash,
                confirmation_hash,
                expected_version,
                status,
                created_at,
                expires_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                proposal_id,
                user_id,
                connection_id,
                operation,
                arguments_json,
                arguments_hash,
                _digest(confirmation_token),
                expected_version,
                "pending",
                now,
                expires_at,
            ),
        )

        db.execute(
            """
            INSERT INTO workspace_requests (
                request_id,
                user_id,
                connection_id,
                proposal_id,
                operation,
                arguments_hash,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                user_id,
                connection_id,
                proposal_id,
                operation,
                arguments_hash,
                "pending",
                now,
                now,
            ),
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

    return {
        "id": proposal_id,
        "connectionId": connection_id,
        "operation": operation,
        "requestId": request_id,
        "confirmationToken": confirmation_token,
        "expiresAt": datetime.fromtimestamp(
    expires_at,
    tz=timezone.utc,
).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def approve_workspace_action(
    user_id,
    connection_id,
    proposal_id,
    confirmation_token,
    request_id,
):
    """Atomically claim a proposal; never dispatch Google writes here."""

    if not all(
        isinstance(value, str) and value
        for value in (
            proposal_id,
            confirmation_token,
            request_id,
        )
    ):
        raise WorkspaceConfirmationError(
            "invalid_confirmation",
            "Invalid confirmation details.",
        )

    now = int(time.time())
    token_hash = _digest(confirmation_token)

    db = get_db()

    try:
        if not _valid_connection(
            db, user_id, connection_id
        ):
            raise WorkspaceConfirmationError(
                "permission_denied",
                "Google account unavailable.",
            )

        result = db.execute(
            """
            UPDATE workspace_proposals
            SET status = 'confirmed',
                confirmed_at = ?
            WHERE proposal_id = ?
              AND user_id = ?
              AND connection_id = ?
              AND confirmation_hash = ?
              AND status = 'pending'
              AND expires_at > ?
              AND EXISTS (
                  SELECT 1
                  FROM workspace_requests
                  WHERE workspace_requests.proposal_id =
                        workspace_proposals.proposal_id
                    AND workspace_requests.request_id = ?
                    AND workspace_requests.user_id = ?
                    AND workspace_requests.connection_id = ?
                    AND workspace_requests.status = 'pending'
              )
            """,
            (
                now,
                proposal_id,
                user_id,
                connection_id,
                token_hash,
                now,
                request_id,
                user_id,
                connection_id,
            ),
        )

        if result.rowcount != 1:
            db.rollback()
            raise WorkspaceConfirmationError(
                "confirmation_unavailable",
                "Confirmation expired, invalid, or already used.",
            )

        result = db.execute(
            """
            UPDATE workspace_requests
            SET status = 'executing',
                updated_at = ?
            WHERE request_id = ?
              AND proposal_id = ?
              AND user_id = ?
              AND connection_id = ?
              AND status = 'pending'
            """,
            (
                now,
                request_id,
                proposal_id,
                user_id,
                connection_id,
            ),
        )

        if result.rowcount != 1:
            db.rollback()
            raise WorkspaceConfirmationError(
                "idempotency_conflict",
                "This request cannot be executed again.",
            )

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

    return {
        "connectionId": connection_id,
        "proposalId": proposal_id,
        "requestId": request_id,
        "status": "claimed",
    }


def get_workspace_request_status(user_id, request_id):
    """Read the persisted state without repeating an operation."""

    db = get_db()

    try:
        row = db.execute(
            """
            SELECT request_id, connection_id,
                   proposal_id, operation,
                   status, result_json, error_code
            FROM workspace_requests
            WHERE user_id = ?
              AND request_id = ?
            """,
            (user_id, request_id),
        ).fetchone()

        if row is None:
            raise WorkspaceConfirmationError(
                "not_found",
                "Workspace request not found.",
            )

        return {
            "requestId": row["request_id"],
            "connectionId": row["connection_id"],
            "proposalId": row["proposal_id"],
            "operation": row["operation"],
            "status": row["status"],
            "result": (
                json.loads(row["result_json"])
                if row["result_json"]
                else None
            ),
            "errorCode": row["error_code"],
        }

    finally:
        db.close()

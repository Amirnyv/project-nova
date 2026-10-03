
"""Execute approved Workspace actions and persist their results."""

import json
import time

from database import get_db
from services.workspace_confirmations import (
    WorkspaceConfirmationError,
    approve_workspace_action,
    get_workspace_request_status,
)


def confirm_calendar_create(
    user_id,
    connection_id,
    proposal_id,
    confirmation_token,
    request_id,
):
    """Execute one previously staged Calendar creation."""

    # Read only the proposal belonging to this user and account.
    db = get_db()
    try:
        row = db.execute(
            """
            SELECT operation, arguments_json
            FROM workspace_proposals
            WHERE proposal_id = ?
              AND user_id = ?
              AND connection_id = ?
              AND status = 'pending'
              AND expires_at > ?
            """,
            (
                proposal_id,
                user_id,
                connection_id,
                int(time.time()),
            ),
        ).fetchone()
    finally:
        db.close()

    if row is None:
        raise WorkspaceConfirmationError(
            "confirmation_unavailable",
            "This proposal is unavailable or has expired.",
        )

    if row["operation"] != "calendar.create":
        raise WorkspaceConfirmationError(
            "unsupported_action",
            "This confirmation does not create an appointment.",
        )

    arguments = json.loads(row["arguments_json"])

    # Validate the stored arguments before claiming execution.
    required = ("summary", "start_time", "end_time", "calendar_id")

    if not all(
        isinstance(arguments.get(key), str)
        and arguments[key]
        for key in required
    ):
        raise WorkspaceConfirmationError(
            "invalid_arguments",
            "The stored appointment is invalid.",
        )

    from services.google_calendar import (
        _calendar,
        _check_calendar_permission,
        _validate_event_times,
    )
    from services.google_credentials import (
        get_google_credentials,
    )

    # Check Google permissions again at confirmation time.
    credentials = get_google_credentials(
        user_id,
        connection_id=connection_id,
    )

    write_scopes = {
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/calendar.events",
    }

    if not set(
    credentials.granted_scopes or credentials.scopes or []
).intersection(write_scopes):
        raise WorkspaceConfirmationError(
            "permission_denied",
            "Google Calendar write permission is unavailable.",
        )

    _validate_event_times(
        arguments["start_time"],
        arguments["end_time"],
    )

    service = _calendar(
        user_id,
        connection_id=connection_id,
    )

    _check_calendar_permission(
        service,
        arguments["calendar_id"],
        write=True,
    )

    # Atomically claim the single-use confirmation.
    approve_workspace_action(
        user_id=user_id,
        connection_id=connection_id,
        proposal_id=proposal_id,
        confirmation_token=confirmation_token,
        request_id=request_id,
    )

    # From this point onward, NEVER blindly retry the write.
    try:
        from services.google_calendar import create_event

        event = create_event(
            user_id=user_id,
            summary=arguments["summary"],
            start_time=arguments["start_time"],
            end_time=arguments["end_time"],
            description=arguments.get("description", ""),
            connection_id=connection_id,
            calendar_id=arguments["calendar_id"],
        )

    except Exception:
        # Google may have created the event before a network failure.
        db = get_db()
        try:
            db.execute(
                """
                UPDATE workspace_requests
                SET status = 'uncertain',
                    error_code = 'provider_outcome_unknown',
                    updated_at = ?
                WHERE request_id = ?
                  AND user_id = ?
                  AND connection_id = ?
                  AND status = 'executing'
                """,
                (
                    int(time.time()),
                    request_id,
                    user_id,
                    connection_id,
                ),
            )
            db.commit()
        finally:
            db.close()

        return get_workspace_request_status(
            user_id,
            request_id,
        )

    # Persist the successful Google result.
    receipt = {
        "eventId": event["id"],
        "summary": event.get("summary", ""),
        "htmlLink": event.get("htmlLink"),
        "calendarId": arguments["calendar_id"],
    }

    db = get_db()
    try:
        db.execute(
            """
            UPDATE workspace_requests
            SET status = 'succeeded',
                result_json = ?,
                updated_at = ?
            WHERE request_id = ?
              AND user_id = ?
              AND connection_id = ?
              AND status = 'executing'
            """,
            (
                json.dumps(receipt),
                int(time.time()),
                request_id,
                user_id,
                connection_id,
            ),
        )
        db.commit()
    finally:
        db.close()

    return get_workspace_request_status(
        user_id,
        request_id,
    )


"""Validate and stage Google Calendar event creation.

Preparing an event never writes to Google Calendar.
"""

from datetime import datetime

from services.workspace_confirmations import (
    WorkspaceConfirmationError,
    stage_workspace_action,
)

from services.google_credentials import (
    get_google_credentials,
    GoogleConnectionError,
)

from services.google_calendar import (
    _calendar,
    _check_calendar_permission,
    CalendarPermissionError,
)

def prepare_calendar_create(
    user_id,
    connection_id,
    summary,
    start_time,
    end_time,
    description="",
    calendar_id="primary",
):
    """Create a single-use proposal for a Calendar event."""

    if not isinstance(summary, str) or not summary.strip():
        raise WorkspaceConfirmationError(
            "invalid_arguments",
            "An appointment title is required.",
        )

    if not isinstance(description, str):
        raise WorkspaceConfirmationError(
            "invalid_arguments",
            "The description must be text.",
        )

    if not isinstance(calendar_id, str) or not calendar_id:
        raise WorkspaceConfirmationError(
            "invalid_arguments",
            "Select a valid calendar.",
        )

    try:
        start = datetime.fromisoformat(
            start_time.replace("Z", "+00:00")
        )
        end = datetime.fromisoformat(
            end_time.replace("Z", "+00:00")
        )

        if (
            start.utcoffset() is None
            or end.utcoffset() is None
            or end <= start
        ):
            raise ValueError

    except (AttributeError, TypeError, ValueError):
        raise WorkspaceConfirmationError(
            "invalid_arguments",
            "Provide valid appointment times with time zones.",
        )


    # Verify the selected account has Calendar write access.
    try:
        credentials = get_google_credentials(
            user_id,
            connection_id=connection_id,
        )

        granted_scopes = set(
    credentials.granted_scopes or credentials.scopes or []
)

        if not granted_scopes:
            raise WorkspaceConfirmationError(
                "permission_denied",
                "Google Calendar permissions could not be verified. Reconnect Google.",
            )

        write_scopes = {
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/calendar.events",
        }

        if not granted_scopes.intersection(write_scopes):
            raise WorkspaceConfirmationError(
                "permission_denied",
                "Reconnect Google to grant Calendar write access.",
            )

        service = _calendar(
            user_id,
            connection_id=connection_id,
        )

        _check_calendar_permission(
            service,
            calendar_id,
            write=True,
        )

    except (GoogleConnectionError, CalendarPermissionError) as exc:
        raise WorkspaceConfirmationError(
            "permission_denied",
            str(exc),
        ) from exc


    arguments = {
        "summary": summary.strip(),
        "start_time": start_time,
        "end_time": end_time,
        "description": description,
        "calendar_id": calendar_id,
    }

    proposal = stage_workspace_action(
        user_id=user_id,
        connection_id=connection_id,
        operation="calendar.create",
        arguments=arguments,
    )

    return {
        "proposal": proposal,
        "eventDraft": {
            "summary": arguments["summary"],
            "description": description,
            "start": {"dateTime": start_time},
            "end": {"dateTime": end_time},
        },
        "message": (
            "Review this appointment and confirm "
            "before I add it to Google Calendar."
        ),
    }

"""Google Calendar operations for Nova's connected accounts."""

from datetime import datetime, timedelta, timezone

from googleapiclient.discovery import build

from services.google_credentials import get_google_credentials


def _calendar(user_id):
    credentials = get_google_credentials(user_id)

    return build(
        "calendar",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )


def list_events(user_id, max_results=20):
    """Retrieve upcoming events from the user's primary calendar."""

    now = datetime.now(timezone.utc).isoformat()

    response = (
        _calendar(user_id)
        .events()
        .list(
            calendarId="primary",
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    return {
        "events": response.get("items", []),
        "next_page_token": response.get("nextPageToken"),
    }


def get_event(user_id, event_id):
    """Retrieve a specific calendar event."""

    return (
        _calendar(user_id)
        .events()
        .get(
            calendarId="primary",
            eventId=event_id,
        )
        .execute()
    )


def create_event(
    user_id,
    summary,
    start_time,
    end_time,
    description="",
):
    """Create a calendar event."""

    event = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_time},
        "end": {"dateTime": end_time},
    }

    return (
        _calendar(user_id)
        .events()
        .insert(
            calendarId="primary",
            body=event,
        )
        .execute()
    )


def update_event(user_id, event_id, updates):
    """Update an existing event."""

    return (
        _calendar(user_id)
        .events()
        .patch(
            calendarId="primary",
            eventId=event_id,
            body=updates,
        )
        .execute()
    )


def delete_event(user_id, event_id):
    """Delete an existing event."""

    (
        _calendar(user_id)
        .events()
        .delete(
            calendarId="primary",
            eventId=event_id,
        )
        .execute()
    )

    return {
        "deleted": True,
        "event_id": event_id,
    }
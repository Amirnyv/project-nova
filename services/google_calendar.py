
"""Google Calendar operations for Nova's connected accounts."""

from datetime import datetime, timezone

from googleapiclient.discovery import build

from services.google_credentials import get_google_credentials


class CalendarValidationError(ValueError):
    """Invalid Calendar request."""


class CalendarPermissionError(PermissionError):
    """The selected calendar does not permit this operation."""


def _calendar(user_id, connection_id=None):
    credentials = get_google_credentials(
        user_id,
        connection_id=connection_id,
    )
    return build(
        "calendar",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )


def _validate_datetime(value):
    if not isinstance(value, str):
        raise CalendarValidationError(
            "Provide an ISO 8601 date and time."
        )

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise CalendarValidationError(
            "Invalid date or time."
        ) from exc

    if parsed.tzinfo is None:
        raise CalendarValidationError(
            "A timezone offset is required."
        )

    return parsed


def _validate_event_times(start_time, end_time):
    start = _validate_datetime(start_time)
    end = _validate_datetime(end_time)

    if end <= start:
        raise CalendarValidationError(
            "The appointment must end after it starts."
        )


def _check_calendar_permission(service, calendar_id, write=False):
    calendar = (
        service.calendarList()
        .get(calendarId=calendar_id)
        .execute()
    )

    role = calendar.get("accessRole")

    if role not in {"owner", "writer", "reader", "freeBusyReader"}:
        raise CalendarPermissionError(
            "Calendar access is unavailable."
        )

    if write and role not in {"owner", "writer"}:
        raise CalendarPermissionError(
            "You cannot modify this calendar."
        )

    return calendar


def list_calendars(user_id, connection_id=None):
    service = _calendar(user_id, connection_id)

    calendars = []
    page_token = None

    while True:
        response = (
            service.calendarList()
            .list(pageToken=page_token)
            .execute()
        )

        for item in response.get("items", []):
            calendars.append({
                "id": item["id"],
                "summary": item.get("summary", ""),
                "time_zone": item.get("timeZone"),
                "writable": item.get("accessRole") in {
                    "owner", "writer"
                },
            })

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return {"calendars": calendars}


def list_events(
    user_id,
    max_results=20,
    connection_id=None,
    calendar_id="primary",
    time_min=None,
    time_max=None,
    page_token=None,
):
    if type(max_results) is not int or not 1 <= max_results <= 250:
        raise CalendarValidationError(
            "max_results must be between 1 and 250."
        )

    if time_min is None:
        time_min = datetime.now(timezone.utc).isoformat()

    start = _validate_datetime(time_min)

    if time_max is not None:
        end = _validate_datetime(time_max)
        if end <= start:
            raise CalendarValidationError(
                "The requested date range is invalid."
            )

    service = _calendar(user_id, connection_id)
    _check_calendar_permission(service, calendar_id)

    params = {
        "calendarId": calendar_id,
        "timeMin": time_min,
        "maxResults": max_results,
        "singleEvents": True,
        "orderBy": "startTime",
    }

    if time_max is not None:
        params["timeMax"] = time_max

    if page_token:
        params["pageToken"] = page_token

    response = service.events().list(**params).execute()

    return {
        "events": response.get("items", []),
        "next_page_token": response.get("nextPageToken"),
    }


def get_event(
    user_id,
    event_id,
    connection_id=None,
    calendar_id="primary",
):
    service = _calendar(user_id, connection_id)
    _check_calendar_permission(service, calendar_id)

    return (
        service.events()
        .get(calendarId=calendar_id, eventId=event_id)
        .execute()
    )


def create_event(
    user_id,
    summary,
    start_time,
    end_time,
    description="",
    connection_id=None,
    calendar_id="primary",
):
    _validate_event_times(start_time, end_time)

    if not isinstance(summary, str) or not summary.strip():
        raise CalendarValidationError(
            "An appointment title is required."
        )

    service = _calendar(user_id, connection_id)
    _check_calendar_permission(service, calendar_id, write=True)

    event = {
        "summary": summary.strip(),
        "description": description,
        "start": {"dateTime": start_time},
        "end": {"dateTime": end_time},
    }

    return (
        service.events()
        .insert(calendarId=calendar_id, body=event)
        .execute()
    )


def update_event(
    user_id,
    event_id,
    updates,
    connection_id=None,
    calendar_id="primary",
):
    if not isinstance(updates, dict) or not updates:
        raise CalendarValidationError(
            "Provide event changes."
        )

    start = updates.get("start")
    end = updates.get("end")

    if start is not None or end is not None:
        if not isinstance(start, dict) or not isinstance(end, dict):
            raise CalendarValidationError(
                "Provide both start and end when rescheduling."
            )

        _validate_event_times(
            start.get("dateTime"),
            end.get("dateTime"),
        )

    service = _calendar(user_id, connection_id)
    _check_calendar_permission(service, calendar_id, write=True)

    return (
        service.events()
        .patch(
            calendarId=calendar_id,
            eventId=event_id,
            body=updates,
        )
        .execute()
    )


def delete_event(
    user_id,
    event_id,
    connection_id=None,
    calendar_id="primary",
):
    service = _calendar(user_id, connection_id)
    _check_calendar_permission(service, calendar_id, write=True)

    service.events().delete(
        calendarId=calendar_id,
        eventId=event_id,
    ).execute()

    return {
        "deleted": True,
        "event_id": event_id,
    }
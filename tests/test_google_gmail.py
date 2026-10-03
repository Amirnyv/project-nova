"""Unit tests for Nova's Gmail integration."""

import base64
from email import message_from_bytes
from unittest.mock import MagicMock, patch

from services import google_gmail


def test_search_messages():
    service = MagicMock()

    request = MagicMock()
    request.execute.return_value = {
        "messages": [{"id": "abc123"}],
        "resultSizeEstimate": 1,
    }
    service.users().messages().list.return_value = request

    with patch.object(google_gmail, "_gmail", return_value=service):
        result = google_gmail.search_messages(1, "is:unread")

    assert result["messages"] == [{"id": "abc123"}]

    service.users().messages().list.assert_called_once_with(
        userId="me",
        q="is:unread",
        maxResults=10,
    )


def test_read_message():
    service = MagicMock()
    encoded = base64.urlsafe_b64encode(b"Hello from Gmail").decode()

    service.users().messages().get().execute.return_value = {
        "id": "abc123",
        "threadId": "thread123",
        "payload": {
            "headers": [
                {"name": "From", "value": "friend@example.com"},
                {"name": "Subject", "value": "Hello"},
                {"name": "Message-ID", "value": "<original@example.com>"},
            ],
            "mimeType": "text/plain",
            "body": {"data": encoded},
        },
    }

    with patch.object(google_gmail, "_gmail", return_value=service):
        result = google_gmail.read_message(1, "abc123")

    assert result["body"] == "Hello from Gmail"
    assert result["subject"] == "Hello"
    assert result["message_id_header"] == "<original@example.com>"


def test_send_email():
    service = MagicMock()
    service.users().messages().send().execute.return_value = {
        "id": "sent123",
        "threadId": "thread123",
    }

    with patch.object(google_gmail, "_gmail", return_value=service):
        result = google_gmail.send_email(
            1, "friend@example.com", "Test subject", "Test body"
        )

    assert result["sent"] is True

    sent = service.users().messages().send.call_args.kwargs
    raw = base64.urlsafe_b64decode(sent["body"]["raw"])
    message = message_from_bytes(raw)

    assert message["To"] == "friend@example.com"
    assert message["Subject"] == "Test subject"
    assert "Test body" in message.get_payload(decode=True).decode()


def test_reply_uses_original_message_id():
    service = MagicMock()
    service.users().messages().send().execute.return_value = {
        "id": "reply123",
        "threadId": "thread123",
    }

    original = {
        "from": "friend@example.com",
        "subject": "Hello",
        "thread_id": "thread123",
        "message_id_header": "<original@example.com>",
        "references": "",
    }

    with (
        patch.object(google_gmail, "_gmail", return_value=service),
        patch.object(google_gmail, "read_message", return_value=original),
    ):
        result = google_gmail.reply_to_message(1, "abc123", "My reply")

    assert result["sent"] is True

    sent = service.users().messages().send.call_args.kwargs
    raw = base64.urlsafe_b64decode(sent["body"]["raw"])
    message = message_from_bytes(raw)

    assert message["In-Reply-To"] == "<original@example.com>"
    assert message["References"] == "<original@example.com>"
    assert sent["body"]["threadId"] == "thread123"


def test_archive_message():
    service = MagicMock()

    request = MagicMock()
    request.execute.return_value = {
        "id": "abc123"
    }
    service.users().messages().modify.return_value = request

    with patch.object(google_gmail, "_gmail", return_value=service):
        result = google_gmail.archive_message(1, "abc123")

    assert result["archived"] is True

    service.users().messages().modify.assert_called_once_with(
        userId="me",
        id="abc123",
        body={"removeLabelIds": ["INBOX"]},
    )


def test_trash_message():
    service = MagicMock()
    service.users().messages().trash().execute.return_value = {
        "id": "abc123"
    }

    with patch.object(google_gmail, "_gmail", return_value=service):
        result = google_gmail.trash_message(1, "abc123")

    assert result["trashed"] is True


def test_modify_labels():
    service = MagicMock()
    service.users().messages().modify().execute.return_value = {
        "id": "abc123",
        "labelIds": ["STARRED"],
    }

    with patch.object(google_gmail, "_gmail", return_value=service):
        result = google_gmail.modify_labels(
            1, "abc123", add_labels=["STARRED"]
        )

    assert result["labels"] == ["STARRED"]

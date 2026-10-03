"""Gmail operations for Nova's connected Google accounts."""

import base64
from email.message import EmailMessage
from email.utils import parseaddr

from googleapiclient.discovery import build

from services.google_credentials import get_google_credentials


def _gmail(user_id):
    credentials = get_google_credentials(user_id)
    return build(
        "gmail",
        "v1",
        credentials=credentials,
        cache_discovery=False,
    )


def search_messages(user_id, query, max_results=10):
    service = _gmail(user_id)

    response = service.users().messages().list(
        userId="me",
        q=query,
        maxResults=max_results,
    ).execute()

    return {
        "messages": response.get("messages", []),
        "result_size_estimate": response.get(
            "resultSizeEstimate", 0
        ),
    }


def read_message(user_id, message_id):
    service = _gmail(user_id)

    message = service.users().messages().get(
        userId="me",
        id=message_id,
        format="full",
    ).execute()

    headers = {
        item["name"].lower(): item["value"]
        for item in message.get("payload", {}).get("headers", [])
    }

    def extract_text(part):
        if part.get("mimeType") == "text/plain":
            encoded = part.get("body", {}).get("data")
            if encoded:
                return base64.urlsafe_b64decode(
                    encoded + "=" * (-len(encoded) % 4)
                ).decode("utf-8", errors="replace")

        for child in part.get("parts", []):
            text = extract_text(child)
            if text:
                return text

        return ""

    return {
        "id": message.get("id"),
        "thread_id": message.get("threadId"),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "subject": headers.get("subject", ""),
        "message_id_header": headers.get("message-id", ""),
"references": headers.get("references", ""),
        "date": headers.get("date", ""),
        "snippet": message.get("snippet", ""),
        "body": extract_text(message.get("payload", {})),
        "labels": message.get("labelIds", []),
    }


def send_email(user_id, to, subject, body):
    address = parseaddr(to)[1]
    if not address or "@" not in address:
        raise ValueError("A valid recipient email is required.")

    message = EmailMessage()
    message["To"] = address
    message["Subject"] = subject
    message.set_content(body)

    encoded = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode("ascii")

    result = _gmail(user_id).users().messages().send(
        userId="me",
        body={"raw": encoded},
    ).execute()

    return {
        "id": result.get("id"),
        "thread_id": result.get("threadId"),
        "sent": True,
    }


def reply_to_message(user_id, message_id, body):
    original = read_message(user_id, message_id)

    sender = parseaddr(original["from"])[1]
    if not sender:
        raise ValueError("Original sender address is missing.")

    subject = original["subject"]
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"

    message = EmailMessage()
    message["To"] = sender
    message["Subject"] = subject
    original_header = original["message_id_header"]

    if original_header:
        message["In-Reply-To"] = original_header
        message["References"] = (
            f'{original["references"]} {original_header}'.strip()
        )

    message.set_content(body)

    encoded = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode("ascii")

    result = _gmail(user_id).users().messages().send(
        userId="me",
        body={
            "raw": encoded,
            "threadId": original["thread_id"],
        },
    ).execute()

    return {
        "id": result.get("id"),
        "thread_id": result.get("threadId"),
        "sent": True,
    }


def archive_message(user_id, message_id):
    result = _gmail(user_id).users().messages().modify(
        userId="me",
        id=message_id,
        body={"removeLabelIds": ["INBOX"]},
    ).execute()

    return {"id": result.get("id"), "archived": True}


def trash_message(user_id, message_id):
    result = _gmail(user_id).users().messages().trash(
        userId="me",
        id=message_id,
    ).execute()

    return {"id": result.get("id"), "trashed": True}


def modify_labels(user_id, message_id, add_labels=None, remove_labels=None):
    result = _gmail(user_id).users().messages().modify(
        userId="me",
        id=message_id,
        body={
            "addLabelIds": add_labels or [],
            "removeLabelIds": remove_labels or [],
        },
    ).execute()

    return {
        "id": result.get("id"),
        "labels": result.get("labelIds", []),
    }

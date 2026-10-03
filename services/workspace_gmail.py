"""Account-bound Gmail preparation and single-use execution for Nova."""

import base64
import hashlib
import json
import time
from email.message import EmailMessage
from email.utils import parseaddr

from googleapiclient.discovery import build

from database import get_db
from services.google_credentials import get_google_credentials
from services.workspace_confirmations import (
    WorkspaceConfirmationError,
    approve_workspace_action,
    get_workspace_request_status,
    stage_workspace_action,
)


def _gmail(user_id, connection_id):
    credentials = get_google_credentials(
        user_id,
        connection_id=connection_id,
    )
    return build(
        "gmail",
        "v1",
        credentials=credentials,
        cache_discovery=False,
    )


def _address(value):
    if not isinstance(value, str) or "\n" in value or "\r" in value:
        raise WorkspaceConfirmationError(
            "invalid_arguments",
            "A valid recipient is required.",
        )

    _, address = parseaddr(value)

    if not address or "@" not in address or not address.split("@")[1]:
        raise WorkspaceConfirmationError(
            "invalid_arguments",
            "A valid recipient is required.",
        )

    return address


def _message_details(service, message_id):
    if (
        not isinstance(message_id, str)
        or not message_id
        or len(message_id) > 200
    ):
        raise WorkspaceConfirmationError(
            "invalid_arguments",
            "A message ID is required.",
        )

    msg = service.users().messages().get(
        userId="me",
        id=message_id,
        format="metadata",
        metadataHeaders=[
            "From",
            "Subject",
            "Message-ID",
            "References",
        ],
    ).execute()

    headers = {
        h["name"].lower(): h["value"]
        for h in msg.get("payload", {}).get("headers", [])
    }

    return msg, headers


def prepare_gmail(
    user_id,
    connection_id,
    operation,
    *,
    to=None,
    subject=None,
    body=None,
    message_id=None,
):
    """Create a reviewable draft without sending anything."""

    if operation not in {"gmail.send", "gmail.reply"}:
        raise WorkspaceConfirmationError(
            "unsupported_action",
            "Unsupported Gmail operation.",
        )

    if (
        not isinstance(body, str)
        or not body.strip()
        or len(body) > 20000
    ):
        raise WorkspaceConfirmationError(
            "invalid_arguments",
            "An email body is required (max 20,000 characters).",
        )

    service = _gmail(user_id, connection_id)

    if operation == "gmail.send":
        recipient = _address(to)

        if (
            not isinstance(subject, str)
            or not subject.strip()
            or len(subject) > 998
            or "\n" in subject
            or "\r" in subject
        ):
            raise WorkspaceConfirmationError(
                "invalid_arguments",
                "A valid subject is required.",
            )

        args = {
            "to": recipient,
            "subject": subject.strip(),
            "body": body,
        }

        draft = dict(args)

    else:
        msg, headers = _message_details(service, message_id)

        recipient = _address(headers.get("from", ""))
        original_subject = headers.get("subject", "")

        reply_subject = (
            original_subject
            if original_subject.lower().startswith("re:")
            else "Re: " + original_subject
        )

        args = {
            "message_id": message_id,
            "to": recipient,
            "subject": reply_subject,
            "body": body,
            "thread_id": msg.get("threadId"),
            "in_reply_to": headers.get("message-id", ""),
            "references": headers.get("references", ""),
        }

        draft = {
            "to": recipient,
            "subject": reply_subject,
            "body": body,
            "inReplyToMessageId": message_id,
        }

    proposal = stage_workspace_action(
        user_id,
        connection_id,
        operation,
        args,
    )

    return {
        "proposal": proposal,
        "mailDraft": draft,
        "message": (
            "Review this email and explicitly confirm "
            "before sending."
        ),
    }


def confirm_gmail(
    user_id,
    connection_id,
    proposal_id,
    confirmation_token,
    request_id,
):
    """Execute one approved Gmail action without automatic retries."""

    db = get_db()

    try:
        row = db.execute(
            """
            SELECT
                p.operation,
                p.arguments_json,
                p.arguments_hash
            FROM workspace_proposals p
            JOIN workspace_requests r
                ON r.proposal_id = p.proposal_id
            WHERE p.proposal_id = ?
              AND p.user_id = ?
              AND p.connection_id = ?
              AND p.status = 'pending'
              AND p.expires_at > ?
              AND r.request_id = ?
              AND r.user_id = ?
              AND r.connection_id = ?
              AND r.status = 'pending'
              AND r.arguments_hash = p.arguments_hash
            """,
            (
                proposal_id,
                user_id,
                connection_id,
                int(time.time()),
                request_id,
                user_id,
                connection_id,
            ),
        ).fetchone()

    finally:
        db.close()

    if row is None or row["operation"] not in {
        "gmail.send",
        "gmail.reply",
    }:
        raise WorkspaceConfirmationError(
            "confirmation_unavailable",
            "This email proposal is unavailable.",
        )

    raw = row["arguments_json"]

    if hashlib.sha256(raw.encode("utf-8")).hexdigest() != row[
        "arguments_hash"
    ]:
        raise WorkspaceConfirmationError(
            "invalid_arguments",
            "Stored email proposal failed integrity verification.",
        )

    args = json.loads(raw)

    _address(args.get("to"))

    if not isinstance(args.get("body"), str) or not args["body"]:
        raise WorkspaceConfirmationError(
            "invalid_arguments",
            "Stored email body is invalid.",
        )

    if (
        not isinstance(args.get("subject"), str)
        or "\r" in args["subject"]
        or "\n" in args["subject"]
    ):
        raise WorkspaceConfirmationError(
            "invalid_arguments",
            "Stored email subject is invalid.",
        )

    service = _gmail(user_id, connection_id)

    message = EmailMessage()
    message["To"] = args["to"]
    message["Subject"] = args["subject"]
    message.set_content(args["body"])

    if row["operation"] == "gmail.reply":
        if (
            not isinstance(args.get("thread_id"), str)
            or not args["thread_id"]
        ):
            raise WorkspaceConfirmationError(
                "invalid_arguments",
                "Stored Gmail thread is invalid.",
            )

        if args.get("in_reply_to"):
            message["In-Reply-To"] = args["in_reply_to"]
            message["References"] = (
                args.get("references", "")
                + " "
                + args["in_reply_to"]
            ).strip()

    payload = {
        "raw": base64.urlsafe_b64encode(
            message.as_bytes()
        ).decode("ascii")
    }

    if row["operation"] == "gmail.reply":
        payload["threadId"] = args["thread_id"]

    # Claim the single-use approval before contacting Gmail.
    approve_workspace_action(
        user_id,
        connection_id,
        proposal_id,
        confirmation_token,
        request_id,
    )

    try:
        result = service.users().messages().send(
            userId="me",
            body=payload,
        ).execute()

    except Exception:
        # Gmail might have sent the email before a network failure.
        # Do not automatically retry.
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

    receipt = {
        "messageId": result.get("id"),
        "threadId": result.get("threadId"),
        "sent": True,
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

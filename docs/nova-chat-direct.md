# Nova Chat Phase 2: direct text backend

This is independent of Nova AI chat, billing and account usernames. No provider
calls or AI usage are involved. No groups, APNs or client UI are implemented.

## Initialization

`init_db()` runs the existing profile migration (social version 1), followed by
`migrate_nova_chat` (version 2). Version 2 adds only `nova_chat_conversations`,
`nova_chat_members`, `nova_chat_messages`, `nova_chat_blocks` and related indexes.
Both social migrations take the same PostgreSQL transaction advisory lock. DDL
and version marker commit together; failed version 2 leaves version 1 intact.
Lock wait is bounded to 5 seconds and migration statements to 60 seconds. A
failed migration stops startup rather than serving with an incomplete schema.
No real application database is changed by the isolated tests.

## API

All routes require the existing Flask session. Use `/api/auth/csrf` with the same
cookie jar, then send `X-CSRF-Token` on every mutation. Responses are JSON with
`Cache-Control: no-store`. Missing login is 401; missing CSRF is 403. Generic
errors use `{error: code, message: safe_message}`; success includes `ok: true`.

All routes have prefix `/api/nova-chat`:

| Method/path | Input | Success fields |
| --- | --- | --- |
| POST `/conversations/direct` | `{recipient_id: "profile-id"}` | `conversation` |
| GET `/conversations` | optional `cursor`, `limit` | `conversations`, `next_cursor`, `has_more` |
| GET `/conversations/{uuid}` | none | `conversation` |
| GET `/conversations/{uuid}/messages` | optional `cursor`, `limit` | `messages`, `next_cursor`, `has_more` |
| POST `/conversations/{uuid}/messages` | `{client_message_id: "uuid", type: "text", text: "..."}` | `message` |
| PUT `/conversations/{uuid}/receipts` | `delivered_through_seq` and/or `read_through_seq` | `last_delivered_seq`, `last_read_seq` |
| GET `/blocks` | optional `cursor`, `limit` | `blocks`, `next_cursor`, `has_more` |
| PUT `/blocks/{profile-id}` | no body needed | `blocked: true` |
| DELETE `/blocks/{profile-id}` | no body needed | `blocked: false` |
| GET `/users` | `username` prefix, 3–30 ASCII handle characters | `users` (at most 20) |

Successful mutations return 200, including idempotent repeats. Profile IDs are
Phase 1 profile IDs serialized as strings, never account IDs. Public identities
contain only `id`, `handle`, `display_name`. Conversation/message IDs and client
retry IDs are UUID strings. Timestamps are UTC ISO-8601. No email or account IDs
are serialized. A profile must be active to use these services. A new DM target
must be discoverable; an existing participant may still reopen an existing DM
after discovery is turned off. Both parties must be active to send/create.

## Ordering, pagination and retries

A transaction locks ordered participant account rows, ordered profile rows,
then the conversation. Block/unblock uses the same participant lock order;
creation serializes before inserting the unique ordered participant pair.
SQLite uses BEGIN IMMEDIATE with foreign keys enabled on service connections.
PostgreSQL writes have bounded lock/statement timeouts. Read operations use a
consistent transaction snapshot so summary watermarks and counts agree.

Sends allocate the next conversation sequence under the lock and commit the
message and metadata together. Identical sender/conversation/client UUID retries
return the original message without consuming another send quota. A changed
text/type returns 409. Membership, profile state and blocks are still checked on
retries: a retry after a block is not a way around it.

Messages default to the newest 50 (maximum 100), returned **oldest to newest within
each page**. The returned cursor fetches the preceding page. Prepend older pages
in the client. Cursors are bounded, validated and scoped to the conversation;
they are not credentials and do not replace membership authorization.

Conversation lists use **creation time descending, then UUID descending**, not
last-message activity sorting. New messages therefore cannot reorder existing
pagination entries. Poll the first page for new conversations; independently
refresh metadata for active conversations. Concurrent creation can appear on a
subsequent refresh. Lists and blocks use bounded keyset pagination, no offsets.
No incremental `after` message endpoint is implemented: clients can refresh the
latest page and deduplicate by message ID, paging backward if needed.

## Receipts and blocking

Sent means committed. Delivered/read are explicit recipient-client acknowledgments,
not push delivery or proof a human read something. Watermarks only increase;
read implies delivered. Positive values must refer to visible committed messages.
There are no per-message-per-recipient receipt rows. Unread counts exclude own
messages and deletion tombstones. Stale lower receipt updates are safe no-ops.

Blocks prevent both directions of DM creation/sending and receipt updates, hide
discovery matches, and suppress peer receipt exposure. Historical messages remain
readable by authorized active members. No API reveals the other party's block
list or block direction. Block/unblock is idempotent. Block takes effect when its
transaction commits: sends serialized before it may succeed; none serialized
after it can succeed until unblocked.

## Limits and remaining boundaries

Text: 1–4,000 characters, at most 16 KiB UTF-8, not whitespace-only or NUL-containing.
Request bodies: 64 KiB. Send quotas: 10/10 seconds and 60/minute per user. New DM
quota: 20/hour/user (existing pair lookups exempt). Search: 30/minute/user.

Sliding quotas use locked files shared by workers on one host. They fail closed
on storage errors, reset if host storage disappears, and do not coordinate
multiple hosts. Multiple instances require a shared limiter before scale-out.
There is no message text or raw exception logging. Rate storage contains only
hashed keys and times. No profile data is automatically published.

Conversation summaries use bounded per-conversation queries; message serialization
also looks up public sender identities. Optimize these reads if measured load
requires it. Retention, reports/moderation workflow, account deletion/anonymization,
and multi-host limits remain launch considerations, not features of Phase 2.
Future account removal must account for RESTRICT participant/member FKs and
separate billing retention. Message sender/creator can be anonymized; history is
not automatically erased.

Phase 3 must define membership history, visibility boundaries, owner transfer,
join/remove/invite authorization, group caps, and shared-group blocking semantics.
The Phase 2 services reject group conversations even though kind/state/role
columns reserve the necessary vocabulary. Do not reuse two-user locking or DM
receipt exposure unchanged for groups.

## Isolated checks

- `venv/bin/python -B -m unittest discover -s tests -p 'test_nova_chat.py' -q`
- `venv/bin/python -B tests/test_nova_chat_postgres.py --postgres-bin /usr/local/opt/postgresql@17/bin`

The PostgreSQL runner reuses the existing scrubbed-environment private-socket
harness; no external database URL is accepted. Its cluster is removed afterward.

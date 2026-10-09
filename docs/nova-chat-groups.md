# Nova Chat Phase 3: group backend

Group behavior is isolated in `services/nova_groups.py` and
`services/nova_group_routes.py`. Existing `/conversations/...` APIs remain
**direct-only**; use `/api/nova-chat/groups` for groups. No billing, AI usage,
iOS UI, push, external service or account-username behavior changes.

## Migration 3

`services/nova_group_schema.py:migrate_nova_groups` runs after social versions
1 and 2 at `init_db()` startup. It uses the same transaction advisory lock as the
other social migrations, 5-second PostgreSQL lock timeout and 60-second statement
timeout (SQLite: BEGIN IMMEDIATE). All DDL and the version marker are atomic.
Failed version 3 rolls back to version 2; completed reruns skip DDL.

Adds to `nova_chat_conversations`: `name` (1–80 characters when present),
`last_event_seq` (nonnegative, default 0), `closed_at` (nullable UTC timestamp).
Adds to `nova_chat_members`: `invited_by` (nullable user FK, SET NULL),
`visible_event_from` (positive, default 1).
Adds a partial unique index allowing at most one active owner per conversation.

Creates `nova_chat_events`: UUID text primary key, conversation FK (CASCADE),
positive per-conversation `seq`, constrained `kind`, nullable actor/target user
FKs (SET NULL), optional bounded `detail`, UTC `created_at`, and unique
`(conversation_id,seq)`. Events include creation, invitation, joining, declining,
removal, leaving, role/ownership changes, renaming and closure. No message bodies
are stored in events. Existing direct rows and sequences are preserved.

Do not run this migration against production without deployment review. PostgreSQL
ALTER TABLE takes brief exclusive locks; startup waits are bounded and failures
stop initialization. Tests use disposable local databases only.

## API contract

Prefix: `/api/nova-chat/groups`. Every endpoint requires the existing authenticated
cookie session. Mutations require `X-CSRF-Token`; obtain it from `/api/auth/csrf`
using the same cookie jar. Responses are JSON, Cache-Control: no-store. There is
no Pro/Max requirement. Auth failure is 401, CSRF/permission denial 403, inaccessible
membership/group 404, validation 400, conflicts 409, and rate limits 429.
Successful requests return 200 with `ok: true` and the fields below.

| Method/path | JSON input / query | Response |
| --- | --- | --- |
| POST `` | `name`, `member_ids` (array of public profile ID strings; may be empty) | `group` |
| GET `` | optional cursor, limit | `groups`, next_cursor, has_more |
| GET `/invitations` | optional cursor, limit | `invitations`, next_cursor, has_more |
| GET `/{id}` | none | `group` with safe member roster |
| PATCH `/{id}` | `name` | name |
| POST `/{id}/members` | `profile_id` | invited |
| POST `/{id}/join` | none | group |
| POST `/{id}/leave` | none | left |
| DELETE `/{id}/members/{profile_id}` | none | removed |
| PATCH `/{id}/members/{profile_id}` | `role`: admin/member | role |
| POST `/{id}/ownership` | `profile_id` | owner public identity |
| GET `/{id}/messages` | optional cursor, limit | messages, next_cursor, has_more |
| POST `/{id}/messages` | client_message_id UUID, type=text, text | message |
| PUT `/{id}/receipts` | delivered_through_seq and/or read_through_seq | last_delivered_seq, last_read_seq |
| GET `/{id}/events` | optional cursor, limit | events, next_cursor, has_more |

Public identities contain only profile ID, handle and display_name. Internal user
IDs, email, phone and passwords are never serialized. Names/text are plain text
for clients to render safely. Group IDs, message IDs and event IDs are UUIDs.

## Membership and permissions

Creation activates the owner and **invites** requested members; nobody is silently
added. Inviting requires the target's active profile and allow_group_invites=true,
and no block in either direction with the inviter. The setting is checked at
invitation time; explicit acceptance is still required. Known public profile IDs
can be invited even when discovery is disabled if invitations are enabled.

Owners/admins can invite, rename and remove ordinary members or invitations.
Admins cannot remove admins or the owner. Only the owner can promote/demote other
active members or transfer ownership to another active, nonsuspended member.
Transfer atomically makes the old owner an admin and the target owner. Owners
cannot demote/remove themselves; transfer first. Ordinary members cannot perform
administration. Blocking does not remove an administrator's management authority.

Invitation acceptance rechecks inviter membership, profile and the block relation.
An invitation whose inviter left or became suspended cannot be accepted; an admin
can cancel and reissue it. A blocked invitation disappears from the invitee's
list. Pending invitees cannot access history or roster. Active members see the
active roster; administrators additionally see pending invitees. Members can leave;
invitees use leave to decline. All membership changes are recorded as events.

An owner must transfer before leaving if any other active member remains. The last
active owner may leave: the group closes, pending invitations are canceled and
history is retained but no longer available through active-member endpoints.

## History, retries, ordering and receipts

Every join/rejoin starts visibility at `last_seq + 1` and `last_event_seq + 1`.
The join event is the first visible event of that tenure. Leaving/removal revokes
all group reads/writes; rejoining never restores the previous tenure's history.
Old cursors cannot bypass these boundaries. Old sender retry IDs remain consumed;
a retry from a prior tenure returns 409 rather than revealing historical content.

Message IDs/retries and limits match Phase 2. A conversation row lock serializes
sequence allocation, membership updates, ownership changes and receipt writes.
Writers acquire sorted account/profile locks before the group lock; no account
locks are acquired afterward. A send serialized before removal may commit;
one serialized after removal cannot. Read transactions use a consistent snapshot;
an already-started read may complete against its pre-removal snapshot.

Messages/events have separate ordered sequences. Pages default to 50, max 100;
within a page they are ascending, with next_cursor fetching older entries.
Group/invitation lists use stable UUID-descending keyset pagination, not activity
ordering; refresh the first page for new data. Cursors never replace authorization.

Receipts are monotonic membership watermarks, reset on rejoin; read implies
delivered. Positive updates must reference an accessible message. Stale lower
updates cannot decrease state. No per-message/per-member receipt table is added.
Blocked peers' receipts are omitted from the roster; pre-join watermarks are
represented as zero. These are client acknowledgments, not proof of human reading.

## Shared-group blocking

Blocking stays private and does not dissolve shared groups. Either-direction
blocks suppress the other person's messages, previews, unread counts and receipts
for that pair. Other members can still communicate and see their permitted
messages. Group sending does not fail merely because another member blocked the
sender. Current membership and administrative events remain visible; block
relationships/direction are never returned. Unblocking can reveal messages within
the current membership tenure. Users can leave or be removed by authorized staff.

## Limits and remaining boundaries

- 50 active members plus pending invitations per group, enforced under the group lock.
- 5 new groups/day/user; 50 new invitations/hour/user.
- 30 management/acceptance operations/hour/user; leaving and declining are exempt.
- Shared DM + group send quotas: 10/10 seconds and 60/minute/user.
- Text: 4,000 characters, 16 KiB UTF-8; request bodies: 64 KiB.

Rate files coordinate workers on one host, not multiple instances. Failed database
writes can consume attempted-action quota; retry sends with an already committed
ID are exempt. Group creation itself has no client retry key: callers should check
the group list after an ambiguous network response before creating again.

This phase does not add reports/moderation operations, account deletion, bans,
invitation expiration, attachments, push, client UI or live delivery. Group
creation/membership events and message history remain stored until a future
retention policy. A suspended sole owner requires future moderation recovery.
The service enforces an owner for every open group; the database index enforces
at most one, not a deferred exactly-one constraint. Multi-host limits, retention
and moderation remain production-release considerations.

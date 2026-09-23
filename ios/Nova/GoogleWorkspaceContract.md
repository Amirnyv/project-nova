# Jarvis Google workspace: proposed native contract

This is a proposal for backend implementation, NOT a deployed route map. No
workspace URL is present in Swift and no Gmail/Calendar operation is sent to
`/chat`. Existing Intel Gmail tools do not establish authenticated iOS APIs.
Calendar operations are not implemented. `UnavailableGoogleWorkspaceService`
is the shipping adapter: every operation is disabled and throws if called.

## Transport and authorization requirements

Backend owners must assign real routes to the operations below before an HTTP
adapter can be added. Reads use authenticated GET; writes use authenticated POST
(or PATCH for editing) with Nova's existing `X-CSRF-Token`. Reuse
`URLSession.shared` and server-owned user identity. Never accept a client user ID.
Every request includes `connectionId`, which must be checked for current-user
ownership, connected state, scopes, and operation-specific permission server-side.
Catalog capabilities and Google identity connection are not authorization grants.

A capabilities response must distinguish installed transport operations from
per-account usable operations and granted scopes. Enable the native operation
set only after a real adapter exists and the server confirms access. Recheck
permissions and ownership on every operation. No direct Google SDK calls or
credential material belong on the phone.

## DTO rules (camelCase keys)

Opaque provider IDs are strings. Connection IDs are integers. Dates are RFC3339
UTC timestamps without fractional seconds (`JSONDecoder.dateDecodingStrategy =
.iso8601`). Calendar timeZone is an IANA identifier. Arrays are always present;
optional fields may be null. The native DTOs are defined in
`GoogleWorkspaceModels.swift`.

- `WorkspaceAddress`: `{name: string|null, email: string}`.
- `WorkspaceMessage`: `{id, threadId, subject, from: WorkspaceAddress,
  to: [WorkspaceAddress], replyTo: [WorkspaceAddress], receivedAt,
  snippet, bodyText: string|null, unread: bool, labelIds: [string]}`.
  Search may omit/null bodyText. Detail returns plain text, not remote HTML.
  No automatic tracking-image loads, script execution, or attachment fetching.
- `WorkspaceCalendar`: `{id, summary, timeZone, writable: bool}`.
- `WorkspaceEvent`: `{id, calendarId, version, title, description: string|null,
  location: string|null, timing: WorkspaceEventTiming, writable: bool}`.
- Timed event timing: `{kind:"timed", start, end, timeZone}` with end > start.
- All-day timing: `{kind:"all_day", startDate:"YYYY-MM-DD",
  endDateExclusive:"YYYY-MM-DD"}`. End is exclusive; do not convert to UTC midnight.
- Paginated reads: `{items: [...], nextPageToken: string|null}`. Tokens are opaque
  and scoped to account/query/date range. Ordering must be deterministic.

## Required operations (route paths intentionally unassigned)

| Operation | Input | Successful response |
| --- | --- | --- |
| gmail.search | connectionId, query, pageToken?; bounded server page size | Page of WorkspaceMessage summaries, newest first |
| gmail.read | connectionId, messageId | WorkspaceMessage including bodyText |
| gmail.send | connectionId, requestId UUID, draft `{to, subject, bodyText, replyToMessageId:null}` | Confirmed provider messageId and threadId |
| gmail.reply | connectionId, requestId UUID, draft with replyToMessageId | Confirmed provider messageId and threadId |
| calendar.list | connectionId | `{items:[WorkspaceCalendar]}` |
| calendar.agenda | connectionId, start inclusive, end exclusive, pageToken? | Page of WorkspaceEvent ordered by start, including overlapping all-day events |
| calendar.read | connectionId, calendarId, eventId | WorkspaceEvent |
| calendar.create | connectionId, calendarId, requestId UUID, draft `{title,description,location,timing,expectedVersion:null}` | Persisted WorkspaceEvent |
| calendar.update | connectionId, calendarId, eventId, requestId UUID, draft with expectedVersion | Persisted WorkspaceEvent with new version |

Reply threading/header construction must happen server-side using the original
owned message. Calendar updates require optimistic concurrency; stale versions
return 409/412 rather than overwriting. Recurrence, attendees/invitations, HTML,
attachments, and destructive actions are deliberately not exposed in this UI.
The registered gmail.archive, gmail.trash, gmail.labels tools are NOT called.
They need separately reviewed read/mutation contracts before native activation.

## Write safety and errors

Explicit native confirmation shows the recipient/subject or event action before
calling the adapter. The backend must enforce any confirmation policy independently
and expose a typed staged-confirmation contract if required; the current protocol
must be extended before enabling such a backend. Never bypass Jarvis confirmations.

requestId is an idempotency key, bound to user/account/operation/payload, persisted
server-side. Same key + same payload returns the original result; changed payload
must fail with conflict. Do not automatically retry uncertain sends/writes.
Future adapters must only return success after confirmed persistence; pending or
confirmation-required responses are NOT success. Drafts currently live in memory,
are not saved to Google/disk, and are discarded when the editor is closed.

Error envelope: `{error:{code:string,message:string,retryable:bool}}` with no
credentials or raw provider diagnostics. Required distinctions: 401 expired Nova
session, 403 missing scope/permission or CSRF, 404 missing owned resource,
409/412 version/idempotency conflict, 429 rate limit with Retry-After, 503 provider
unavailable. UI must retain drafts on failure and allow account reauthorization.

## OAuth remains unchanged

See `Connections.md` for inspected implementation and exact secure single-use
browser handoff requirements. Keep manual same-account browser login, Done/back
to Nova, and authoritative connection refresh. No callback scheme, handoff token,
or new OAuth endpoint has been invented. Server callback must validate stored
expected state before exchange; automatic return requires an agreed universal-link
or callback contract. Unpushed Gmail/Calendar scope work is not presumed deployed.

## Focused native verification

Run `sh ios/Nova/Verification/check-workspace.sh` on macOS with Xcode installed.
This standalone Swift harness tests the real DTO and view-model sources using
injected services. Fixtures exist only in Verification, outside the synchronized
app source directory. No XCTest target was added to the existing app project.

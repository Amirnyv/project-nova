# Nova Apple billing backend

This implementation uses `app-store-server-library==3.1.2`, Apple's official
Python library, for App Store Server API JWT authentication and Apple JWS
certificate-chain/signature verification. Online certificate checks are enabled.
No Apple credentials, certificates, or signed purchase payloads are bundled.

Official references:
- https://github.com/apple/app-store-server-library-python/tree/v3.1.2
- https://www.apple.com/certificateauthority/

## Configuration

Required server configuration:

| Variable | Purpose |
| --- | --- |
| `APPLE_KEY_ID` | In-App Purchase signing key identifier |
| `APPLE_ISSUER_ID` | App Store Connect issuer identifier |
| `APPLE_PRIVATE_KEY_PATH` | Read-only secret-file path to the `.p8` key |
| `APPLE_ROOT_CA_PATHS` | Comma-separated paths to Apple root CA certificates in DER format |

Public defaults (override only with the same Nova identifiers):

- `APPLE_BUNDLE_ID=com.amirnyv.Nova`
- `APPLE_APP_ID=6817116419`
- `APPLE_ENVIRONMENT=Production`; the only alternative is `Sandbox`.

The official verifier requires trusted root certificates; it does not bundle
roots or use the general HTTPS trust store for JWS verification. Obtain the
Apple roots from Apple's PKI site, review them, and provision read-only files.
Never trust a root supplied in a request. Maintain certificate rotation as an
operational responsibility. `APPLE_ROOT_CA_PATHS` is therefore necessary with
this architecture. `APPLE_SANDBOX_USER_IDS` is not used.

Mount the private key through the deployment's secret-file mechanism. Never
commit it, put its contents in source, print it, or include it in test fixtures.
Missing configuration returns a sanitized 503 on verification requests. It does
not prevent Stripe usage or require Apple initialization during module import.

## iOS contract

The repository has no separate M2 StoreKit contract to inspect. Align the client
with these exact requests. Use the existing authenticated Flask session cookie
and Nova's existing CSRF token in `X-CSRF-Token` for authenticated POSTs. These
routes do not introduce bearer-token authentication. Missing login follows
Flask-Login's existing login redirect behavior in the real app.

1. Before purchase, POST `/api/billing/apple/account-token` with JSON `{}`.
   Response: `{"ok":true,"app_account_token":"<server UUID>"}`.
   Pass this UUID to StoreKit's `.appAccountToken(...)` purchase option. Fetch it
   for the currently logged-in Nova account; never reuse it after account switch.
2. After a verified StoreKit purchase, transaction update, or Restore Purchases,
   POST `/api/billing/apple/sync` with only:
   `{"signed_transaction":"<StoreKit transaction JWS representation>"}`.
   No `plan`, `status`, `user_id`, `environment`, or success boolean is accepted.
3. The backend verifies the supplied JWS, fetches current subscription status,
   verifies its transaction and renewal JWS, binds ownership, and reconciles.
   Finish the StoreKit transaction after successful synchronization. On transient
   503s, retry with bounded client backoff; do not initiate another purchase.

A successful sync has this shape (illustrative placeholders, not purchase data):

```json
{
  "ok": true,
  "sync": "reconciled",
  "subscription": {
    "plan": "max",
    "status": "active",
    "billing_source": "apple",
    "active_billing_sources": ["apple", "web"],
    "current_period_start": "<UTC ISO-8601>",
    "current_period_end": "<UTC ISO-8601>",
    "cancel_at_period_end": 0
  },
  "apple_subscriptions": [{
    "plan": "max",
    "status": "active",
    "environment": "Production",
    "expires_at": "<UTC ISO-8601>",
    "renewal_at": "<UTC ISO-8601>",
    "auto_renews": true
  }],
  "multiple_billing_sources": true,
  "management": {
    "apple": "https://apps.apple.com/account/subscriptions",
    "web": "/create-portal-session"
  }
}
```

`sync` may be `stale` for an already-applied or older verified snapshot; this is
an idempotent success, not an error. Effective access may be `none`/`inactive`
even though synchronization succeeded. Dates, renewal status, and management
links may be null. Apple states include active, grace, expired, billing_retry,
revoked, superseded, unsupported_product, and unknown. Grace uses Apple's signed
grace expiration for access, retaining the actual renewal date separately.

Errors use `{"ok":false,"error":{"code":"...","message":"safe text"}}`.
400: invalid request, verification failure, unsupported presented product.
409: ownership conflict or account-token binding required.
503: missing configuration, temporary verification/API failure, or DB failure.
No error includes raw provider errors, signed payloads, paths, or secrets.
Existing CSRF errors retain the application's existing 403 response format.
After sync failure, `/api/ai/usage` remains the source of existing effective
access; the client must not discard independently valid web access.

## Ownership and reconciliation

Only `nova.pro.monthly` (pro) and `nova.max.monthly` (max) grant Apple access.
A new lineage requires the Apple-signed account token to map to the authenticated
Nova user. A UUID supplied outside the signed transaction has no authority.
Previously bound tokenless lineages may restore only to their recorded owner.
First-claim tokenless purchases require a separately reviewed support/migration
process; the backend deliberately does not provide an insecure first-claim path.
Family Sharing is not supported by this one-owner model and is rejected. Do not
enable it for these products without a separate entitlement design.

Database uniqueness and row locks (PostgreSQL) / `BEGIN IMMEDIATE` (SQLite) make
ownership, transaction upserts, subscription changes, and notification processing
atomic. Original ownership never silently transfers. A signed-state timestamp
prevents older snapshots from replacing newer state. Current provider API status
is authoritative; the notification event name alone never grants access.

The effective tier remains developer > max > pro/paid, with Stripe preferred on
equal tiers and one selected allowance/period, never combined quotas. Stripe SQL
and checkout behavior are unchanged. Apple failures grant/extend nothing and do
not erase previously verified records or independent Stripe entitlements.
Previously verified Apple access remains bounded by its stored expiry; revocation
updates depend on notification delivery or a subsequent verified sync.

## Notifications V2

Configure later, after staging verification:
`https://workfieldhq.com/api/billing/apple/notifications`

POST body: `{"signedPayload":"<Apple JWS>"}`. No Nova login/CSRF is required.
The signature, bundle, app ID, and configured environment are verified first.
Signed UUID deduplication commits with state. Transient Apple/DB failures return
503 and leave the UUID unprocessed, allowing Apple retries. Duplicate deliveries
are acknowledged. Signed TEST notifications are recorded without an API lookup.
Common subscription lifecycle notifications refresh current signed status rather
than blindly translating event names; delayed older refunds therefore cannot
revoke newer valid purchases. Notifications with no known account token/owner are
acknowledged as `unbound` without granting access; later authenticated sync fetches
current state. No signed payload is stored or logged.

This endpoint handles subscription transaction notifications and TEST. Summary-only
or non-subscription payloads are rejected; it does not implement Apple's refund
consumption-information responses or external-purchase workflows. Monitor failures
and missed delivery; notification-history recovery/scheduled reconciliation is not
implemented in this change.

## Sandbox and App Review

Use an isolated staging deployment/database configured `APPLE_ENVIRONMENT=Sandbox`
with genuine Apple sandbox transactions and matching certificates/credentials.
Production never automatically retries against sandbox or accepts Xcode/local
unsigned transactions. Sandbox rows cannot grant Production access, even if a
configuration change points at a database containing them. Keep staging databases
separate rather than switching environment on a live database.

The M2 client's TestFlight/App Review purchase testing must be routed deliberately
to the sandbox-capable deployment. A Production-only endpoint will reject sandbox
purchases. Resolve that client/backend routing before submission; do not temporarily
switch the production service to Sandbox or add a database-user allowlist.

## Deployment and rollback checklist (not executed here)

1. Install the pinned dependency and validate dependency resolution in a staging
   environment. The local tests use mocked SDK verification/network boundaries.
2. Back up the database. Test both billing migrations against a restored staging
   PostgreSQL copy. Disposable PostgreSQL 17.11 testing now passes; see
   `billing-postgres-validation.md` for evidence and remaining production checks.
3. Provision reviewed Apple root DER files and the secret `.p8` file securely.
4. Startup `init_db()` runs migration 1 and then migration 2. Migration 2 adds
   `apple_account_tokens`, environment/outcome fields, and Apple renewal/state
   metadata. It preserves Stripe/Apple records and is transactional/repeatable.
   Pending migrations take an exclusive subscription-table lock; completed migrations
   skip it. Pending DDL uses a 5-second lock timeout and 60-second per-statement
   timeout: schedule a quiet deployment window and retry safely if blocked.
5. Verify iOS account token, Pro/Max purchases, restore, account switching,
   duplicate requests, cancellation, grace, expiry, refund, upgrade/downgrade,
   mixed web/Apple access, TEST notifications, retries, and out-of-order deliveries.
6. Verify unchanged Stripe checkout, portal, webhook, legacy paid users, and
   `/api/ai/usage`. Compare preserved Stripe records before/after Apple sync.
7. Only then configure production credentials/notification URL and deploy through
   the normal reviewed process. No such operations were performed in this task.

Rollback must retain a backend compatible with multi-provider subscriptions.
Do not roll back to the old one-row-per-user writer or drop Apple ownership data.
If Apple must be disabled operationally, route it to a safe retryable maintenance
response while preserving billing records; do not return successful notifications
without processing them. Keep Stripe serving independently. Restoring an old DB
snapshot can lose ownership/deduplication and must be coordinated with replay.

## Local tests (no app import, credentials, production DB, or paid APIs)

```sh
venv/bin/python -B -m unittest discover -s tests -p test_apple_billing.py -v
venv/bin/python -B -m unittest discover -s tests -p test_billing_foundation.py -v
venv/bin/python -B -m unittest discover -s tests -q
venv/bin/python -B -m unittest test_workspace_security -q
```

Do not run `python app.py`, import `app`, or run initialization against an unknown
`DATABASE_URL` merely to test billing. The isolated tests construct temporary SQLite
fixtures and compile selected Flask handlers rather than executing app startup.

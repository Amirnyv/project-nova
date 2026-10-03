# Isolated production integration candidate — 2026-10-02

Worktree: `/private/tmp/nova-production-integration`
Branch: `integration/production-20261002`
Base: freshly fetched `origin/main`, `76d4cf4`.
Status: **Paper Trading contract implemented; ready for final pre-deployment review.**

See `paper-trading.md` for the current results (180 discovery tests, 11 explicit
PostgreSQL tests), schema, execution policies and review limitations. The original
integration checkpoint results below are retained as historical evidence.
No commit, push, main update, Render action, or production database connection.

## Integration

38 explicitly allowlisted files transferred from the feature working tree.
Common-base three-way content integration retained main changes; four app.py
conflicts were resolved around Jarvis imports, routing confirmations, persistence
and planner context. Main router module and iOS tree are unchanged. Legacy portfolio writes now share
the atomic Paper Trading writer; see paper-trading.md. The Apple service implementations and migration contract were
preserved. Frontend Jarvis/Connections changes were transferred as a matched set.

Workspace initialization now runs after billing migrations in init_db, using the
same injected connection factory/backend as startup. Imports are deferred to
avoid circular initialization. OAuth rejects missing/mismatched saved state before
token exchange; state and PKCE verifier are consumed on callback, and the verified
saved state is supplied to the exchange. Tests cover sequential callback replay.

Old tests expecting legacy conversational Gmail authorization now assert that it
is rejected, even with confirmed=True. Registry/status expectations include the
existing Calendar capabilities. No approval behavior was weakened.

## Validation

- 41 Python files compiled successfully.
- Full discovery: 154 tests, 145 passed, 9 opt-in PostgreSQL tests skipped.
- Explicit PostgreSQL run: all 9 passed, PostgreSQL 17.11.
- Workspace security: 5 passed separately.
- Billing foundation: 14 passed separately (also in discovery).
- Apple integration: 40 passed separately (also in discovery).
- New integration security: 6 tests included in discovery (5 OAuth, 1 startup).
- New offline Gunicorn app-loader smoke: 1 passed, with scrubbed environment,
  dotenv disabled, outbound connects prohibited and temporary SQLite database.
  This is app loading via Gunicorn, not a live multiworker HTTP load test.
- JavaScriptCore frontend regression passed: syntax, CSRF, hostile stored text,
  Open Project handler. Whitespace diff check passed.
- Real downloaded-backup rehearsal passed against this candidate: all 3 Stripe
  subscriptions and 8 user records preserved; IDs, original fields, sequences,
  migration markers 1/2, Apple schema/indexes/constraints and repeated init_db
  passed. Restored cluster/extracted copy deleted, original checksum unchanged.
  Source backup PostgreSQL 18.6; test server 17.11; ownership/ACL not restored.
- Original 38 allowlisted file hashes unchanged after integration.

Expected failure-path tests emit synthetic error/warning messages. No failing
assertions remain in the performed validation. No real Apple/Google/provider
credentials or provider requests were used.

## Pending before final deployment review

Paper Trading's five endpoints now match the supplied M2 contract. Actual native
client testing remains a final review step; see paper-trading.md.

Browser/native end-to-end tests, real provider verification and multiworker
confirmation behavior remain unverified. Legacy Jarvis conversational confirmations
remain memory-based as before. The integrated Workspace tables were created in
repeated startup during rehearsal; production lock behavior at load is unmeasured.

The source tree is deliberately unstaged/uncommitted. Retain the original dirty
worktree as the checkpoint. Do not deploy or update main without final review and explicit approval.

## Artifact exclusions

No feature database history was merged. No backups, SQLite files, exports, .env,
private keys, PEM files, caches or credentials were transferred for inclusion.
New ignore patterns supplement main's existing exclusions. Local test harnesses
and restored copies were not retained as candidate source.

## Exact candidate file inventory relative to origin/main

- `.gitignore`
- `app.py`
- `database.py`
- `docs/apple-billing.md`
- `docs/billing-postgres-validation.md`
- `requirements.txt`
- `services/apple_billing.py`
- `services/apple_gateway.py`
- `services/apple_routes.py`
- `services/apple_schema.py`
- `services/billing_entitlements.py`
- `services/billing_schema.py`
- `services/connection_vault.py`
- `services/google_calendar.py`
- `services/google_credentials.py`
- `services/google_gmail.py`
- `services/google_oauth.py`
- `services/jarvis_confirmations.py`
- `services/jarvis_planner.py`
- `services/jarvis_tools.py`
- `services/workspace_confirmations.py`
- `services/workspace_execute.py`
- `services/workspace_gmail.py`
- `services/workspace_prepare.py`
- `services/workspace_schema.py`
- `static/css/nova_v3.css`
- `static/js/nova_v3.js`
- `templates/index_v3.html`
- `test_workspace_security.py`
- `tests/test_apple_billing.py`
- `tests/test_billing_foundation.py`
- `tests/test_billing_postgres.py`
- `tests/test_google_gmail.py`
- `tests/test_integration_security.py`
- `tests/test_isolated_startup.py`
- `tests/test_jarvis_confirmations.py`
- `tests/test_jarvis_planner.py`
- `tests/test_jarvis_project_resolution.py`
- `tests/test_jarvis_status.py`
- `tests/test_jarvis_tools.py`
- `tests/test_launch_hardening.py`
- `docs/integration-candidate.md` (this report)

## Paper Trading continuation file changes

- `agents/portfolio_agent.py`
- `app.py`
- `database.py`
- `services/paper_schema.py`
- `services/paper_trading.py`
- `services/paper_routes.py`
- `tests/test_paper_trading.py`
- `tests/test_billing_postgres.py`
- `docs/paper-trading.md`
- `docs/integration-candidate.md`

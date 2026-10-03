# PostgreSQL billing migration validation

Validated on disposable PostgreSQL 17.11 (Homebrew, Intel macOS). No production
connection, backup, .env, Apple key, Flask import, or provider call was used.
The harness clears inherited environment, uses synthetic data, starts its own
private Unix-socket-only cluster, and stops/removes that cluster afterward.
Homebrew's default cluster is not used and no PostgreSQL service was enabled.

## Results and scope

- Nine real PostgreSQL integration tests pass using AST-extracted, unmodified
  database connection wrappers and init_postgres_db/init_db startup functions.
- Legacy Pro, Max, canceled and inactive subscriptions across four users retain
  all rows, IDs and original fields (except intentional blank-provider inference).
  The subscription sequence retains its position and the next insert uses ID 41.
- Provider-specific identity and legacy-row uniqueness, Apple token/transaction/
  notification ownership constraints, indexes and immutable-owner trigger work.
- Duplicate legacy identifiers abort atomically without dropping records; a
  corrected synthetic conflict can be retried successfully.
- Injected failures in both migrations roll back their individual DDL/data.
  Failure in migration 2 leaves valid committed migration 1; init_db retries
  successfully. Concurrent migration workers and repeat startup pass.
- An open reader blocks pending DDL; migration aborts around five seconds and
  can be retried. Completed startup succeeds with that reader still present.
  Transaction-local timeouts reset after commit.
- Billing foundation: 14 tests pass. Apple integration: 40 tests pass, using
  simulated Apple verification responses, not real Apple signing credentials.

In the actual code, the one-row-per-user conversion is **migration 1** in
services/billing_schema.py. **Migration 2** in services/apple_schema.py adds
account tokens and Apple environment/state metadata. Both were validated.

## Safety changes

The migrations now check completed markers before requesting an exclusive
subscriptions lock. Pending migrations still recheck markers under that lock.
Transaction-local lock_timeout=5s and statement_timeout=60s bound each wait/
statement. No billing business rules or schema design were changed.

## Deployment conditions and recovery

This establishes PostgreSQL compatibility for the representative fixtures, not
compatibility with an uninspected production schema or every production row.
Before deployment:

1. Restore the fresh logical backup into an isolated staging database matching
   production's PostgreSQL major version. Verify the restore includes schema,
   data, sequences and migration markers. Do not point staging at production.
2. Run these migrations against that copy and compare subscription IDs, every
   Stripe field, row counts, sequence positions, constraints and migration markers.
   Resolve conflicting identifiers through review; never discard billing rows.
3. Review the exact uncommitted deployment diff and run billing/Apple tests in
   the deployment runtime. Confirm the backup restore procedure actually works.
4. Schedule a quiet maintenance window. Stop/drain app workers and subscription
   writers; run one controlled initialization with the reviewed code before
   restarting normal workers. Do not allow old one-row-per-user writers to run
   alongside the migrated application. init_db includes existing unrelated base
   schema work, so the new timeouts do not bound the entire startup process.
5. Verify markers 1 and 2, preserved Stripe data, usage entitlements and Stripe
   webhook/portal/checkout behavior, then perform the reviewed Apple smoke tests.
   Monitor startup failures and webhook retries before ending maintenance.

Pending DDL holds ACCESS EXCLUSIVE on subscriptions until each migration commits,
blocking readers and writers. Normal index construction and Apple-table DDL also
acquire locks. The 60-second limit is per statement, not total migration time;
production duration cannot be predicted from these tiny fixtures. A timeout
fails startup rather than silently proceeding with incomplete billing tables.
Completed migrations avoid the exclusive subscription lock.

Prefer a forward retry after resolving a lock/conflict: each migration is atomic,
although the two migrations are separate transactions. If full restoration is
necessary, stop all writers, preserve a separate copy of the failed/current
state, and restore the verified pre-deployment logical backup into a clean
replacement database with tooling appropriate to its format (pg_restore for an
archive, psql for plain SQL), configured to stop on errors. Validate schema,
rows, sequences and ownership before switching service connections. Pair the
restored schema with the corresponding reviewed pre-deployment code. Never
simply run the old one-row-per-user code against migrated data. Reconcile billing
changes after the backup and replay/reconcile provider notifications: restoring
an older backup loses post-backup data and deduplication records.

No production restore, deployment, or credential/configuration change was made.
Production backup rehearsal and real-data conflict checks remain deployment gates.

## Reproduce locally

```sh
venv/bin/python -B tests/test_billing_postgres.py --postgres-bin /usr/local/opt/postgresql@17/bin
venv/bin/python -B -m unittest discover -s tests -p test_billing_foundation.py
venv/bin/python -B -m unittest discover -s tests -p test_apple_billing.py
```

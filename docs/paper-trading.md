# Native Paper Trading API — integration candidate

Implemented from the supplied M2 iOS contract. All actions are simulated; the
only external integration is the existing Twelve Data market-data reader.
No brokerage library, credentials, or order-execution endpoint is used.

## HTTP contract

All five routes use the existing authenticated Nova session. Anonymous calls
return JSON 401 with `error=unauthenticated`. POST requires the existing session
CSRF token in X-CSRF-Token. Errors contain `error` and `message`; unexpected
internal failures return a generic JSON 503. Every response has Cache-Control:
no-store. POST bodies require exactly the documented string fields; supplied
prices, user IDs and unknown fields are rejected.

- GET /api/markets/paper/portfolio: USD virtual account, holdings, recent trades,
  aggregate values and exact supported_symbols: SPY, QQQ, AAPL, TSLA, NVDA, AMZN,
  MSFT. First account has $10,000. Unavailable valuations are null, not fabricated.
- GET /api/markets/paper/transactions?before=<positive integer>: descending stable
  transaction IDs, strict id < cursor, 50 per page, next_before or null.
- POST /api/markets/paper/preview: symbol, side BUY/SELL, unit dollars/shares,
  amount. Computes quantity, balance/holding availability, total and realized P/L
  from a server quote. Returns persisted preview_id and epoch expires_at.
- POST /api/markets/paper/trades: preview_id only. Serializes on the authenticated
  user, checks quote/expiry/availability, and commits trade/balances/result together.
  Completed retries return the stored original JSON, including original cash,
  without another quote request or trade. IDs cannot be used by another user.
- POST /api/markets/paper/reset: exact confirmation RESET PAPER PORTFOLIO. Removes
  holdings and visible trade history; restores 10000 virtual cash. Invalidates
  pending previews. Completed preview results are retained for retry safety and
  do not recreate reset history or alter the restored cash.

Decimal fields are plain decimal strings. IDs are JSON integers; simulation is
boolean; expires_at is numeric. Dates are UTC ISO8601 with timezone offsets.

## Explicit execution policy

- Preview lifetime: 120 seconds, checked again after fetching the fill quote.
- Quote age: provider epoch timestamp required, 0 through 900 seconds old.
  Missing, future, stale or invalid quotes fail closed. Receipt time is never
  substituted for market timestamp. Quote symbol must match the requested symbol.
- Market hours: fills require Twelve Data is_market_open=true. No invented
  holiday calendar or extended-hours permission. Missing status fails closed.
- Quote-change tolerance: zero; any Decimal price change invalidates that preview
  permanently and requires another review.
- Shares: six decimals. Dollars convert downward to six share decimals. Dollar
  budgets truncate to cents first. Cash totals round half-up to cents; sub-cent
  trades are rejected. No commissions, fees, shorting, leverage or negative cash.
- Average cost is retained to eight decimal places for new trades. Existing
  DOUBLE PRECISION/SQLite REAL storage is preserved; decimal arithmetic/string
  formatting occurs at boundaries. This is not an exact-decimal database ledger.
- Historical trades without metadata reconstruct weighted average cost using
  the old cent-rounded average policy. Naive legacy timestamps assume the old
  server clock was UTC; historical timezone cannot be proven from stored values.
- Day P/L uses New York calendar dates: opening shares * (current - prior close)
  plus today's signed fill quantities * current price minus signed rounded fill
  cash flows. Missing/current-day-incompatible quotes, missing prior close, or
  legacy trades with uncertain timing yield null. No historical day P/L is guessed.

The quote adapter uses the existing get_json('quote', ...) integration and fresh
requests for preview/fill. It does not change the existing Markets quote cache.
Quote metadata reference: https://twelvedata.com/docs and official Twelve Data
quote API models. No real provider request was made during local validation.

## Shared data and migration

Existing portfolios, positions, trades and their IDs/data are retained. Legacy
chat buy_stock/sell_stock now call the same locked writer, returning the existing
chat result keys. No competing portfolio system was introduced. Chat continues
to use its existing server-side quote path; the strict preview freshness/review
policy applies to the new native API.

Additive initialize_paper_schema runs after existing startup migrations:

- paper_previews: unique opaque preview ID, user FK, expiry, reviewed payload,
  persisted execution result and invalidation flag; user index.
- paper_trade_details: unique trade FK, user FK and decimal realized P/L text.

SQLite initialization uses BEGIN IMMEDIATE; PostgreSQL uses an advisory
transaction lock, 5-second lock timeout and 60-second statement timeout. DDL is
transactional and repeatable; no old table is rebuilt or old row backfilled.
Billing migration markers remain 1 and 2, unchanged. Paper schema uses idempotent
additive initialization, not a billing migration version.

Writes serialize on a users row lock in PostgreSQL and BEGIN IMMEDIATE in SQLite.
Balance validation, trade insert and completed-preview persistence are atomic.
Reset and legacy chat trades use the same lock convention. Transient failures
roll back, permitting a safe retry. Quotes fetched during execution hold that
user's lock for the bounded upstream request duration.

## Validation and remaining review

24 dedicated SQLite/Flask Paper Trading tests passed. Two additional real
PostgreSQL tests cover concurrent duplicate execution, chat interoperability,
isolation, repeat initialization, reset and injected failure rollback.
Full Python discovery: 180 tests, 169 passed and 11 opt-in PostgreSQL tests skipped;
explicit PostgreSQL run: all 11 passed. Workspace security: 5 passed separately;
billing foundation: 14 passed; Apple billing: 40 passed. Frontend regression,
Gunicorn app-loader smoke, compilation of 45 Python files and diff whitespace pass.

Real-backup rehearsal passed: all 8 existing portfolios preserved exactly,
plus 8 users and 3 Stripe subscriptions. That backup had zero positions/trades;
nonempty history preservation was exercised with synthetic legacy fixtures.
New paper tables were empty after migration and repeated startup succeeded.
The restored cluster/extracted copy was removed and backup checksum unchanged.
Backup PostgreSQL 18.6; local test server 17.11. Ownership/ACL were excluded locally.

Ready for final pre-deployment review, not automatic deployment approval.
Still manually test the actual M2 client, actual market subscription timestamp/
market-open availability, pending/filled retry UI after reset, six-decimal display,
and account switching. Exact PostgreSQL 18 and live multiworker/load testing were
not performed. Repeated portfolio valuation/history reads and uncached quote calls
should be monitored for provider quotas and large-history performance.

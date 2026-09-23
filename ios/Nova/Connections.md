# Native Connections

Contracts were inspected read-only in `origin/feature/jarvis-phase-1` at
`90fad39`. They are absent from this branch's Python backend; deploy the
corresponding backend separately. No backend changes are included here.

- `GET /api/connections`: `{connections: [...]}` with id, provider,
  provider_account_id, display_name, status, connection_type, and timestamps.
- `GET /api/connections/capabilities`: `{providers: [...]}` with provider,
  display_name, connection_type, oauth, connected, services, and accounts.
  Service entries contain id, display_name, capabilities. These are catalog
  capabilities, not proof of granted permissions or available execution tools.
- `GET /api/connections/google/connect`: authenticated browser authorization
  entry. Stores OAuth state and PKCE verifier in the browser's Flask session.
- No disconnect endpoint was found.

Native API reads retain `URLSession.shared` authentication. The system Safari
view has a separate cookie jar; native cookies are NOT exported or injected.
The user must sign into the same Nova account in that browser if necessary.
Because login returns to `/app` rather than the requested setup route, the user
may need to close and reopen Google setup once after browser login. This is a
manual reauthentication fallback, not seamless native session handoff. A browser
already signed into another Nova account can target that other account; users
must verify their browser account. Native status always reads the native account.

The browser return to `/app` is not intercepted as OAuth success. Done, sheet
dismissal, and app activation refresh authoritative native account data. There
is no invented callback scheme or credential persistence.

## Backend dependencies / release checks

- A server-issued, short-lived, single-use browser handoff tied to the current
  Nova user is needed for a seamless account-bound native flow.
- An agreed native callback/universal-link contract is needed for automatic return.
- The inspected callback reads `expected_state` but does not compare it with
  `supplied_state`; backend owners must review/fix OAuth state validation before
  production rollout. No native workaround grants authorization.
- Google currently requests identity scopes only. Gmail/Calendar operations
  and permissions must not be inferred from the capability catalog.
- Test same-account browser login, different-account browser sessions, consent,
  denial, pending status, server configuration errors, Done/swipe dismissal,
  session expiry, and foreground refresh on a physical iPhone.

No native XCTest target exists in the current Xcode project. Simulator compilation
is validation of the native code, not verification of deployed OAuth behavior.

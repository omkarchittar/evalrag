# EvalRAG console implementation

Build the Next.js console against the authenticated, persisted API. Use the same-origin proxy, HttpOnly sessions and in-memory CSRF token. Workspace membership controls editing; a global administrator does not bypass workspace membership.

1. Shared authentication, responsive navigation and accessible loading/error/empty states.
2. Workspace dashboard, memberships, knowledge-base creation, upload/ingestion polling, document downloads and paginated chunk inspection.
3. Playground with configured model/prompt/retrieval controls, grounded answer and explicit abstention, source/quote inspection, saved query history and tool/usage trace.
4. Versioned case editor, immutable evaluation submission/results and compatible baseline/candidate regression comparison. Unknown metrics remain unknown with coverage.
5. Real PostgreSQL + API + worker + production Next browser verification using a clearly identified controlled provider, mobile and accessibility checks, screenshots. This is integration evidence, not live AI quality measurement.
6. Production image/Compose/CI definitions, setup and deployment documentation. Verify what the local environment supports and record remaining runtime/live-provider work explicitly.

Meaningful checks: protected routes and session expiry; viewer controls and direct API rejection; upload to indexed document; cited query and source inspection; abstention and provider errors; dataset version conflict; run idempotency and comparison missing-cost coverage; mobile overflow/keyboard/accessibility. Keep source inputs and credentials out of logs. Review the feature independently before committing.

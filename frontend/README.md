# EvalRAG research console

Next.js App Router + React + TypeScript. The console uses real FastAPI records for workspace membership, indexed evidence, query traces, datasets and evaluation comparisons. It has no demo-data fallback.

```sh
npm ci
npm run dev
```

Open `http://localhost:3000`. Start the API on port 8000 and a separate worker as described in the [root README](../README.md). Bootstrap an administrator before signing in.

`EVALRAG_API_URL` selects the internal backend upstream (default `http://127.0.0.1:8000`). Rewrites capture it **at build time**, so rebuild when changing upstreams. The browser calls same-origin `/api` routes, stores no bearer token, and keeps only the session’s CSRF token in memory. No provider key belongs in this application or a `NEXT_PUBLIC_` variable.

```sh
npm run lint
npm run typecheck
npm run format:check
npm run build
npm start
```

The build packages public/static assets into `.next/standalone`; `npm start` serves that production output on port 3000. Typography uses local system fallbacks and requires no third-party font requests.

## Browser verification

Install backend development dependencies into `../backend/.venv` and provide a dedicated PostgreSQL 17 test database with pgvector available. The database role must have `CREATEDB` permission: the fixture creates and drops its own temporary database.

```sh
npx playwright install chromium
TEST_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@localhost:5432/evalrag_test' npm run test:e2e
```

Tests launch an isolated API (18080), a separate worker, a controlled HTTP provider and a production Next server (3110). Those ports must be free. The provider supplies deterministic fixture responses for transport/contract verification; it is not a live-model quality benchmark. Artifacts go to git-ignored `test-results/` and `playwright-report/`.

Journeys cover upload/indexing, citation/source inspection, history, abstention, tools and explicit provider failures; versioned editing and conflict/reload behavior; semantic evaluation and unknown-cost comparison; viewer restrictions and revoked sessions; self-demotion; mobile layout and axe accessibility checks.

# EvalRAG

A RAG engineering workbench for grounded answers, reproducible experiments and regression analysis.

**Status: backend and research console implemented; live benchmark and release verification in progress.**
The console connects indexed documents, grounded query traces, versioned datasets and immutable experiments.
Provider quality measurements and a verified deployed release remain outstanding.

## Implemented and verified

- Responsive Next.js research console: workspaces, document/chunk inspection, configurable playground, source citations, tool traces, datasets, evaluations and comparison gates.
- Cookie sessions with CSRF protection, hashed API tokens, database-backed login throttling and administrative account management.
- Workspace-scoped knowledge-base APIs with owner/editor/viewer permissions and attachment downloads.
- Separate ingestion worker with heartbeat, crash recovery, atomic indexing and actual embedding usage.
- PDF, UTF-8 text and Markdown extraction with input limits and page provenance. PDFs run in an isolated process with decoded-stream budgets, a 10-second wall timeout, CPU limits, RSS monitoring, and a hard address-space limit on Linux.
- Fixed-token and recursive chunking with Unicode-safe boundaries, capped at 2,000 chunks and 250,000 embedding tokens per document.
- Checksum-idempotent ingestion and transactional pgvector indexing.
- Validated OpenAI embedding adapter supporting small and large embedding models.
- Grounded query API with pgvector retrieval, structured cited claims, explicit abstention and immutable query history.
- Bounded agent loop with document search, arithmetic and scoped metadata lookup; per-call receipts and cumulative context limits.
- Actual model/token/latency observations with versioned, source-linked cost estimates and explicit unknown-usage handling.
- Versioned dataset APIs, fixed experiment snapshots and resumable evaluation jobs with per-case traces.
- Actual embedding similarity and separately estimated semantic support, with evaluator usage and protocol provenance.
- Retrieval metrics, operational percentiles and coverage-aware regression gates.
- [60-case authored benchmark](benchmarks/README.md), two embedding configurations and API-based import/run/report/compare commands.
- Database-enforced immutability of experiment inputs and completed observations.
- PostgreSQL job queue with SKIP LOCKED claims, expiring leases, backoff and stale-worker fencing.
- FastAPI liveness/readiness, structured request logs, correlation IDs and Prometheus metrics.
- Alembic migrations, reproducible dependency locks, non-root Dockerfile and backend CI definition.

Current local verification: **185 backend tests against PostgreSQL 17 and 7 production-build browser journeys pass**.
Lint, TypeScript, formatting and schema checks pass. Browser checks include responsive layout, axe accessibility,
version conflicts, permissions, source inspection, semantic-run wiring and comparison coverage.
These controlled-provider results are not live AI quality measurements. The same seven browser journeys also pass against the Linux/arm64 Docker Compose stack. Live-model benchmarks and remote publication remain unverified.

![EvalRAG research dashboard](docs/screenshots/dashboard.png)

[Playground and source evidence](docs/screenshots/playground.png) · [Evaluation results](docs/screenshots/evaluation.png) · [Comparison](docs/screenshots/comparison.png) · [Mobile](docs/screenshots/mobile.png).
Screenshots use fictional data and a controlled provider; see [provenance](docs/screenshots/README.md).

## Product walkthrough

![Recorded EvalRAG walkthrough](docs/demo.gif)

Fictional evidence and a controlled local model fixture. This demonstrates application behavior, not live AI quality. [Recording provenance and regeneration](docs/demo.md).

## Architecture

See [architecture and tradeoffs](docs/architecture.md) for the component diagram,
relational invariants and security/reliability design. The [source PRD](docs/PRD.md)
is preserved from the supplied Word document. The [implementation plan](docs/implementation-plan.md)
tracks the complete scope and evidence.

## Run with Docker

Requires Docker Compose. From the repository root:

```sh
cp .env.example .env
# Set a local PostgreSQL password and provider key in .env.
docker compose up --build
```

Bootstrap an administrator with the command below, then open `http://localhost:3000` for the console.
`http://localhost:8000/docs` exposes the API schema for local development.
`/health/live` checks the process; `/health/ready` checks the database and migration
version table; `/metrics` exports request counts and latency histograms. Ports bind
only to localhost. Keep `/metrics` internal behind the deployment gateway.

Compose starts PostgreSQL, runs the migrations as a separate one-shot service and
then starts the API, a separate durable worker and the Next.js console.
See [deployment and operations](docs/deployment.md) for HTTPS, secrets, proxy and rollout configuration.

## Native development

Use Python 3.12+ and PostgreSQL 17 with the pgvector extension installed.
Create a dedicated database and user, then:

```sh
cd backend
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.lock
.venv/bin/pip install --no-deps -e .
export EVALRAG_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@localhost:5432/evalrag'
.venv/bin/alembic upgrade head
.venv/bin/uvicorn evalrag.app:create_app --factory --reload --port 8000 --no-access-log
```

Secrets belong in environment variables or a git-ignored `backend/.env` for native
runs. Never commit API keys, encryption keys or real business documents.

Start the console in another terminal (Node.js 24):

```sh
cd frontend
npm ci
npm run dev
```

The default API upstream is `http://127.0.0.1:8000`; the browser uses same-origin `/api` routes.
See the [frontend guide](frontend/README.md) for production builds and browser checks.

## Accounts and worker configuration

Create the first administrator using the interactive password prompt:

```sh
docker compose exec api python -m evalrag.cli create-user --email admin@example.com --name Admin --role admin
# Native equivalent, from backend:
.venv/bin/python -m evalrag.cli create-user --email admin@example.com --name Admin --role admin
```

Use `POST /api/auth/token` for API-client authentication or `/api/auth/login` for an
HttpOnly browser session. Cookie mutations require an allowed `Origin` and the
returned `X-CSRF-Token`. Administrators can provision accounts at `/api/admin/users`.
There are no built-in passwords or open public signup. See [API usage](docs/api.md).

Run the worker in a second terminal with the same database and provider configuration:

```sh
cd backend
.venv/bin/python -m evalrag.worker
# Process at most one eligible job and exit:
.venv/bin/python -m evalrag.worker --once
```

Set `EVALRAG_OPENAI_API_KEY` for model calls. Missing credentials produce explicit
failed jobs; they do not return synthetic responses. Retryable provider errors use
bounded exponential backoff; lease loss prevents stale results from being committed.

## Verify changes

Point `TEST_DATABASE_URL` at a separate test database, never a live database:

```sh
export TEST_DATABASE_URL='postgresql+psycopg://USER:PASSWORD@localhost:5432/evalrag_test'
./scripts/check.sh
```

The script checks formatting/lint, upgrades migrations, checks schema drift, and runs
the suite. Database tests skip explicitly if `TEST_DATABASE_URL` is absent; a run
without it does not verify PostgreSQL behavior. CI supplies PostgreSQL and also
checks migration downgrade/upgrade and Docker image compilation.

Test fixture provider responses are controlled HTTP responses used to exercise
adapter contracts. They are not fabricated live model quality results.

## Remaining release work

Measured live-provider benchmark runs with failure analysis; remote image publishing and public deployment. Local Linux/arm64 Docker runtime verification passes all seven browser journeys. The [implementation plan](docs/implementation-plan.md) records completed checkpoints and the remaining PRD scope.

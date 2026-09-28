# EvalRAG

A RAG engineering workbench for grounded answers, reproducible experiments and regression analysis.

**Status: grounded queries, durable evaluations and benchmark tooling implemented; frontend/release work in progress.**
The product APIs are usable through OpenAPI or an API client. The frontend and measured live-model
benchmark/release package are still in progress.

## Implemented and verified

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

Current local verification: **185 tests pass against PostgreSQL 17**. This count includes unit, HTTP and database tests; it is not a claim that
the final PRD benchmark/scenario requirements have been completed. Live provider calls
and Docker image builds have not yet been verified in this environment.

## Architecture

See [architecture and tradeoffs](docs/architecture.md) for the component diagram,
relational invariants and security/reliability design. The [source PRD](docs/PRD.md)
is preserved from the supplied Word document. The [implementation plan](docs/implementation-plan.md)
tracks the complete scope and evidence.

## Run the current backend with Docker

Requires Docker Compose. From the repository root:

```sh
cp .env.example .env
# Set a local PostgreSQL password and provider key in .env.
docker compose up --build
```

Open `http://localhost:8000/docs` for the current API schema.
`/health/live` checks the process; `/health/ready` checks the database and migration
version table; `/metrics` exports request counts and latency histograms. Ports bind
only to localhost. Keep `/metrics` internal behind the deployment gateway.

Compose starts PostgreSQL, runs the migrations as a separate one-shot service and
then starts the API and a separate durable worker. The frontend is not yet included.

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

## Next milestones

Next.js frontend; browser tests; measured live-provider benchmark runs; release pipeline; screenshots and demo GIF.

The final release will include measured benchmarks, an interactive frontend,
architecture/state diagrams, screenshots, a demo GIF, deployment instructions and
an explanation of failure cases and design decisions.

# Deployment and operations

The supplied Compose definition runs PostgreSQL/pgvector, a one-shot Alembic migration, FastAPI, a separate durable worker and the Next.js console. Container definitions and CI jobs are provided; local Docker execution remains unverified until a Docker runtime is available. Native browser verification uses the actual production Next build and separate backend processes.

## Local startup

1. Copy `.env.example` to `.env`. Set `POSTGRES_PASSWORD` and `EVALRAG_OPENAI_API_KEY`.
2. Run `docker compose up --build`.
3. Bootstrap an account with `docker compose exec api python -m evalrag.cli create-user --email admin@example.com --name Admin --role admin`. Enter its password at the prompt.
4. Open `http://localhost:3000`. Create a workspace, add a knowledge base, upload documents and wait for `ready`.
5. Ask a question in the playground, author reference cases in Evaluations and start an experiment.

No public signup or default accounts exist. Admin status manages deployment accounts; workspace owner/editor/viewer permissions are independent. A global admin does not bypass workspace membership.

## HTTPS deployment

- Put an HTTPS gateway in front of the console. Set `EVALRAG_ENVIRONMENT=production` and `EVALRAG_ALLOWED_ORIGINS` to a JSON array containing the exact public HTTPS origin. Production cookies are Secure, HttpOnly and SameSite=Strict. A production cookie cannot authenticate a plain HTTP local browser.
- Keep the database, API, worker and provider credentials private. Expose only the console through the gateway. Restrict API `/docs`, `/metrics` and health endpoints to operators; do not publish the API’s port directly.
- Build the console with `EVALRAG_API_URL=http://api:8000` (the Compose default). This is a build-time rewrite destination, not a runtime browser configuration. Changing it requires a new build.
- Supply the same database/model/base-URL configuration to API and worker. Model keys stay in a secret manager or backend environment. Never pass them into Next’s build or public variables.
- Permit long-running query requests at the gateway. The API provider timeout defaults to 45 seconds per call and agent mode may make several bounded calls. Worker evaluation runs finish independently of browser connections.
- The Next proxy accepts up to 51 MB to accommodate the API’s maximum configured 50 MB upload plus multipart overhead. `EVALRAG_UPLOAD_LIMIT_BYTES` remains the authoritative backend limit. Set the gateway limit accordingly; parser/token/chunk limits remain independent.

Login throttling uses the direct connection address. Behind a shared Next proxy, the IP budget is shared by that proxy’s users, while account budgets remain separate. Do not trust arbitrary forwarded IP headers to bypass limits. Configure trusted edge identity before changing this policy for a larger deployment.

## Rollout and recovery

Run migrations once before replacing API/worker instances. Take a PostgreSQL backup first and test restoring it into an isolated environment. Schema downgrades can remove data; use reviewed migrations or a tested restore plan for production rollback.

The worker leases jobs with heartbeats, retry backoff and stale-worker fencing. Keep at least one worker running. Compose gives it a 60-second shutdown grace period; interrupted work resumes through queue recovery. Ingestion and evaluation failures retain explicit status/error codes.

Monitor `/health/ready`, request latency/error metrics, failed jobs, evaluation progress and database storage. Health readiness is not proof that model credentials or quota work: validate a small upload/query using the intended provider before opening access. Unknown provider pricing remains `Unknown` and comparison gates remain inconclusive when cost coverage is incomplete.

## Build and release checks

GitHub Actions runs backend lint/tests/schema/migration checks against PostgreSQL 17 with pgvector, frontend lint/type/format checks and real browser journeys against a production build, then compiles both images. Image jobs do not push or deploy. A published release and a tested deployment remain separate acceptance work; the current workflow must not be described as a verified production deployment.

Browser artifact fixtures are fictional. Screenshots demonstrate product wiring and UI behavior, not measured live AI quality. Use the benchmark CLI and retain the resulting reports for real provider measurements.

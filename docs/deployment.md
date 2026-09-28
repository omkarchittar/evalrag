# Deployment and operations

The supplied Compose definition runs PostgreSQL/pgvector, a one-shot Alembic migration, FastAPI, a separate durable worker and the Next.js console. Both images build and all seven browser journeys pass against the local Linux/arm64 Compose stack, including migrations, the separate worker and containerized PostgreSQL/pgvector. The model endpoint uses controlled fictional fixtures; this verifies packaging and service integration. Live-provider measurements, amd64 execution, remote image publication and public HTTPS deployment remain unverified.

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

GitHub Actions runs backend lint/tests/schema/migration checks against PostgreSQL 17 with pgvector, frontend lint/type/format checks and real browser journeys against a production build, then compiles both images. CI image jobs only compile images. The separate tag-triggered workflow below publishes after the complete quality gate. Local container verification has passed; remote publication and public HTTPS deployment still require execution evidence.

Browser artifact fixtures are fictional. Screenshots demonstrate product wiring and UI behavior, not measured live AI quality. Use the benchmark CLI and retain the resulting reports for real provider measurements.

## Versioned image publishing

The `Publish verified images` workflow starts on a pushed `v*` tag. It calls the complete quality workflow for that exact tagged commit before publishing API and console images to GHCR. API and worker use the same image. Publishing has package-write permission only in the publishing job; pull-request CI remains read-only. Actions in the publishing job are commit-pinned. Images include source/revision metadata, BuildKit provenance and SBOMs, and are built for Linux amd64/arm64. No mutable `latest` tag is created.

The workflow uses GitHub's documented [reusable workflow](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows) and [container publishing](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images) mechanisms. The definitions have been locally checked; successful remote publishing still needs execution evidence.

After a successful tag run, copy each image digest from its job summary into the deployment secret/environment configuration:

```sh
export EVALRAG_API_IMAGE='ghcr.io/OWNER/evalrag-api@sha256:API_DIGEST'
export EVALRAG_CONSOLE_IMAGE='ghcr.io/OWNER/evalrag-console@sha256:CONSOLE_DIGEST'
docker compose -f compose.yaml -f compose.release.yaml pull
docker compose -f compose.yaml -f compose.release.yaml up --no-build -d
```

The release override intentionally keeps the same migrations, health checks, environment, volumes and worker wiring as local Compose. Set actual digest values; the placeholders above are documentation, not runnable image references. Tag names can be moved by repository writers, so deploy by digest and protect release tags in repository settings. For rollback, retain the previous digest pair and confirm schema compatibility before replacing services. If a matrix publication fails after one image is pushed, do not deploy that partial release; require the whole workflow to succeed.

Public HTTPS infrastructure and deployment credentials are environment-specific and are not provisioned by image publication. A registry upload is not evidence of a running deployment.

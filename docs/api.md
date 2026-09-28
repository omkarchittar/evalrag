# Current backend API

The OpenAPI schema at `/docs` is the authoritative request/response reference.
This guide covers implemented ingestion, grounded queries and durable evaluations.

## Authentication and access

Bootstrap an administrator using `python -m evalrag.cli create-user`. A password
is read from a hidden terminal prompt, or from the environment variable named by
`--password-env`. Account creation validates email, role and password before writing.

`POST /api/auth/token` accepts `email` and `password` and returns an opaque bearer
`access_token`. Supply it as `Authorization: Bearer TOKEN`. Store tokens securely;
they are credentials, even though only their SHA-256 digests persist in the database.
`POST /api/auth/logout` revokes the current session. Sessions expire after 12 hours
by default, and disabling a user or changing their role revokes their sessions.

Browser clients use `/api/auth/login`, `/api/auth/me`, and `/api/auth/logout`.
Login sets an HttpOnly, SameSite=Strict session cookie and returns a CSRF token.
Send `Origin` and `X-CSRF-Token` on cookie-authenticated mutations. Allowed origins
are configured by `EVALRAG_ALLOWED_ORIGINS` as a JSON array. Set
`EVALRAG_ENVIRONMENT=production` behind HTTPS to enable Secure cookies.

Administrators manage accounts through `/api/admin/users`. Global administrator
status does not bypass workspace membership. Owner, editor and viewer permissions
are scoped independently to each workspace. Owners manage workspace membership;
editors and owners upload documents and create knowledge bases; viewers can read.

## Index documents

1. `POST /api/workspaces` with `{"name":"Policy research"}`.
2. `POST /api/workspaces/{workspace_id}/knowledge-bases` with a name and embedding/
   chunk settings. Defaults and supported ranges appear in OpenAPI.
3. Upload multipart field `file` to `POST /api/knowledge-bases/{id}/documents`.
4. Poll `GET /api/knowledge-bases/{id}/documents` for `queued`, `processing`, `ready`
   or `failed`. Failures expose a safe error code. A running worker and provider key
   are required to progress beyond queued.
5. Read `GET /api/documents/{id}/chunks` for page, ordinal and source text, or
   download the original from `/api/documents/{id}/download`.

PDF, UTF-8 TXT and Markdown are supported. Scans without extractable text require
OCR before upload. Default upload size is 10 MB, with separate decoded-PDF, text,
page, memory, CPU, chunk-count and embedding-token limits. Repeating the same bytes
within a knowledge base reuses the existing document and job, even if renamed.

The worker commits a complete vector index and the successful job outcome together.
Provider calls run outside database transactions. Heartbeats maintain the lease;
final writes require current ownership. Transient provider failures back off within
the attempt budget; permanent errors and exhausted leases mark the document failed.
The current API does not yet provide retry commands for terminal ingestion failures.

`GET /api/workspaces/{id}/overview` reports stored document and query observations.
Embedding tokens on documents are provider-reported usage; no cost is inferred from
unversioned pricing. Empty query metrics mean no query observations exist yet.

## Operations

`/health/live`, `/health/ready`, and `/metrics` are operational endpoints. Keep the
metrics route internal at your gateway. Logs contain request/job IDs and safe error
codes, not prompts or document contents. Request body limits run before JSON and
multipart parsing; normal application errors include a correlated request ID.

The current suite verifies contracts with controlled provider responses. Live model
quality, production load and Docker execution require separate release validation.

## Grounded queries and trace inspection

`POST /api/knowledge-bases/{id}/queries` accepts a question and optional configuration:

```json
{
  "question": "What is the retention period?",
  "config": {
    "top_k": 5,
    "minimum_score": 0,
    "prompt_version": "grounded-v1",
    "agent_mode": false
  }
}
```

Omitted model settings use the deployment's `EVALRAG_GENERATION_MODEL`. Additional
models must be explicitly listed in `EVALRAG_ADDITIONAL_GENERATION_MODELS` (JSON array).
`GET /api/query-options` reports available models, prompts and limits. Unknown prices
remain unknown even when a model is enabled. See [cost provenance](pricing.md).

A 201 response means a trace was persisted; inspect `outcome` (`answered`, `abstained`,
or `error`) and `error_code`. The response contains the answer, claim-level citations,
retrieved chunks with cosine scores/provenance, actual usage, cost estimates and tool
receipts. Query history is paginated at `GET /api/knowledge-bases/{id}/queries`.
`GET /api/query-traces/{trace_id}` reads one immutable observation. All routes require
workspace membership; global administrators have no implicit workspace access.

Each claim must cite a supplied chunk and a nonempty quote found in that chunk.
An invented source or quote withholds the complete answer, records validation details
and reports explicit abstention. Citation checks establish source/quote existence;
they do not prove that the quote semantically entails the claim. Semantic evaluation
is a separate layer. No matching evidence produces an abstention without a generation
call in normal query mode.

Agent mode permits document search, bounded arithmetic and metadata lookup. Every
call records input, output, duration and failure state. A query can execute at most
three tools and four completions; unknown tools and malformed arguments cannot run.
Search and metadata access remain scoped to the same knowledge base. A cumulative
24,000-token source budget excludes duplicate content: subsequent searches return
references to chunks already supplied. Repeated provider-call IDs are rejected.

Provider calls release DB transactions. Authorization is checked again for retrieval,
metadata and final persistence; revocation during a query prevents returning its answer.
Only configured provider adapters run in the product. Automated test fixtures simulate
provider responses for contract testing and are not a live-model quality benchmark.

## Datasets, evaluations and regression gates

Create datasets at `POST /api/workspaces/{id}/datasets` with a name. `GET /api/datasets/{id}`
returns a version and cases. Replace the complete case list using `PUT /api/datasets/{id}/cases`
with `{"version": CURRENT_VERSION, "cases": [...]}`. A stale version returns 409; successful edits
increment it. Cases support question, reference answer, SHA-256 document checksums in `expected_sources`,
optional `expected_abstention`, expected tool, tags and notes. See OpenAPI for limits (200 cases/run).
`GET /api/datasets/{id}/export` returns portable labels without internal case IDs. Owners and editors
can edit and schedule experiments; viewers can inspect results.

Queue a run with `POST /api/workspaces/{id}/evaluation-runs` and a unique `Idempotency-Key` header:

```json
{
  "dataset_id": "DATASET_ID",
  "knowledge_base_id": "KNOWLEDGE_BASE_ID",
  "name": "Baseline / top 5",
  "query": {"top_k": 5, "prompt_version": "grounded-v1", "agent_mode": true},
  "evaluate_semantics": true
}
```

The worker processes `queued` → `running` → `completed` or `failed`. Read status/configuration/input
snapshots at `GET /api/evaluation-runs/{id}` and page case observations at `/results`. Every result
links to its complete immutable query trace. Reads and writes remain scoped to workspace membership.
Runs preserve dataset revision, original cases, corpus/index digests, query/prompt settings, evaluator
protocol and an opaque provider fingerprint. Current access and input identity are rechecked before
execution and completion. Retries resume unfinished cases; exhausted jobs become explicitly failed.

`GET /api/evaluation-runs/{candidate_id}/compare/{baseline_id}` requires completed runs sharing the
same logical dataset/corpus and evaluation protocol. It reports per-metric deltas, regression flags,
quality/cost coverage, thresholds and a three-way outcome: pass, regression, or inconclusive. Lost
scores, reduced quality coverage, incomplete cost coverage or evaluator failures prevent a passing
gate. Query/embedding/prompt configurations can differ; evaluator protocol must remain consistent.
Quality tolerances are absolute (default 0.05); latency/cost tolerances are relative (default 0.2).

See [benchmark commands and metric definitions](../benchmarks/README.md). The bundle contains authored
labels; no live-provider accuracy claims are inferred from its existence or from contract tests.

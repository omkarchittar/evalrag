# EvalRAG implementation plan

**Goal:** Implement the complete supplied PRD as a reliable portfolio project.
**Architecture:** Modular FastAPI application, independent durable worker, PostgreSQL,
and Next.js frontend. Domain rules do not depend on HTTP or model providers.
**Tech stack:** Python 3.12+, SQLAlchemy 2, Alembic, FastAPI, PostgreSQL, Next.js, TypeScript.
**Spec:** [architecture.md](architecture.md); source acceptance criteria: [PRD.md](PRD.md).

## Global constraints

No placeholder product behavior. No fabricated metrics. Real Postgres integration tests.
Sensitive values never appear in logs. APIs validate and authorize every mutation.
Keep the full PRD scope intact across iterations. Implement core backend before UI polish.

## Review focus

Malformed/oversized files; model outputs without evidence; concurrency and retries;
expired/forged credentials; changed inputs after a saved approval or evaluation snapshot.
Each is covered by tests in the owning task below and checked again through HTTP.

## Execution

Implement inline in this session, with behavior tests preceding domain implementation.
User explicitly authorized scaffolding and backend implementation; proceed without
adding intermediate approval gates. Record actual test results here, not intentions.

### 1. Foundation and schema

- [x] Deliverable: `config.py, db.py, models.py, migrations`.
- [x] Behavior evidence: Constraints reject duplicate document checksums and cross-workspace references; migrations upgrade and downgrade on PostgreSQL.
- [x] Run the backend suite (`.venv/bin/pytest`) and relevant integration/browser checks.
- [x] Commit the verified increment and record evidence below.

### 2. Ingestion and vector indexing

- [x] Deliverable: `ingestion.py, providers.py, worker.py`.
- [x] Behavior evidence: PDF/TXT/Markdown parsing preserves provenance; token overlap terminates; duplicate ingestion reuses the record; actual pgvector ranking returns expected chunks.
- [x] Run the backend suite (`.venv/bin/pytest`) and relevant integration/browser checks.
- [x] Commit the verified increment and record evidence below.

### 3. Grounded query and tools

- [x] Deliverable: `rag.py, tools.py, api.py`.
- [x] Behavior evidence: Unsupported citations and arithmetic attacks fail closed; abstention is explicit; query trace stores actual usage/latency/cost.
- [x] Run the backend suite (`.venv/bin/pytest`) and relevant integration/browser checks.
- [x] Commit the verified increment and record evidence below.

### 4. Evaluation and regression

- [x] Deliverable: `evaluation.py, benchmarks/`.
- [x] Behavior evidence: 50–100 cases with references; immutable run snapshots; known precision/recall/rank metrics; failed cases affect error rate; comparable run regression gates.
- [x] Run the backend suite (`.venv/bin/pytest`) and relevant integration/browser checks.
- [x] Commit the verified increment and record evidence below.

### 5. Frontend and operational delivery

- [x] Research console, persisted API integration, production browser journeys and screenshots.
- [x] Local Linux/arm64 container verification, release workflow definitions and demo GIF.
- [ ] Live-provider measurements, remote publishing and public deployment verification.
- [ ] Deliverable: `frontend/, Dockerfile, compose.yaml, .github/workflows/`.
- [ ] Behavior evidence: Browser journey for ingestion/query/evaluation/comparison; responsive accessible UI; CI and builds pass; screenshots and GIF reflect real runtime.
- [ ] Run the backend suite (`.venv/bin/pytest`) and relevant integration/browser checks.
- [ ] Commit the verified increment and record evidence below.

## Evidence ledger

- 2026-09-28: Read both source PRDs, verified remote repository empty, cloned independent repository, preserved source requirements and architecture. Implementation in progress.

### Backend increment — 2026-09-28

- Foundation schema and domain services committed locally.
- PostgreSQL 17 + pgvector 0.8.6 installed for actual integration tests on local port 55432.
- Verified: 67 tests, 91% statement coverage; Ruff passes; Alembic schema check passes; full downgrade to base then upgrade succeeds.
- Queue concurrency test uses separate PostgreSQL transactions and proves SKIP LOCKED gives different jobs to different workers.
- API currently exposes only operational endpoints. Authentication and product endpoints remain pending.
- Docker Compose and CI definitions are present but not executed locally (Docker is unavailable).
- Neither frontend, complete benchmark corpus, live model quality, screenshots, GIF nor release deployment is complete.
- Next: authenticated APIs and worker orchestration; continue through all remaining PRD requirements.

### Reviewed foundation checkpoint

- Independent review found concrete lease-timing, authority-cache, PDF memory, chunk-amplification and model-identity issues. All applicable findings were reproduced and fixed; no review findings deferred.
- Final suite for this checkpoint: **79 passing tests** with PostgreSQL, with no skipped tests.
- Real Uvicorn readiness and Prometheus endpoints returned successful responses; smoke-test servers were stopped afterward.
- Current status: foundation complete, broader product implementation remains active. No remote push or release deployment has been performed.

### Authenticated API and durable-worker checkpoint — 2026-09-28

- Cookie/Bearer authentication, CSRF, persisted login throttles, bootstrap CLI and account administration implemented. Password validation errors omit input values.
- Scoped workspace/member/knowledge-base/document APIs, downloads, chunk views and persisted overview added.
- Ingestion runs in a separately launched worker. Provider IO releases database transactions; final indexing and job completion are atomic and fenced by the lease. Usage is actual provider-reported embedding tokens.
- Queue recovery marks exhausted/failed documents explicitly. Supported upload-size configuration propagates through PDF parsing and indexing; PDF memory/CPU/decoded-content limits remain independent.
- Full suite: **103 passing tests**, no skips, with PostgreSQL 17. Ruff lint/format and Alembic schema check pass. Full downgrade to base and upgrade to head pass on the isolated test database.
- Native Uvicorn smoke test in a temporary database verifies CLI bootstrap, real HTTP authentication, persisted product mutation, separate-worker missing-key failure handling, and session revocation. Temporary processes and database removed afterward.
- Independent review found three concrete issues across the increment (blank evidence quotes, bootstrap validation secret exposure, PDF upload-size mismatch). Regression tests reproduced all three; fixes approved on re-review with no outstanding findings.
- Compose now starts the worker and shares backend configuration. FlowPilot dependency locks include psutil. YAML and environment references validated, but actual Docker builds/startup remain unverified because Docker is unavailable.
- These test totals are not live provider quality metrics or the final PRD benchmark corpus. Frontend, complete benchmark artifacts and release presentation remain outstanding. No remote push or deployment performed.

### Grounded query and tools checkpoint — 2026-09-28

- Added exact cosine retrieval scoped to knowledge base/index/ready documents, with provenance, threshold/top-k settings and optional fixed-corpus filtering for evaluation.
- Added strict-schema generation, cited claim validation and explicit abstention. Source/quote validity is explicitly separate from semantic entailment, which remains for the evaluation layer.
- Added an allowlisted agent loop for search, calculator and metadata, bounded to three tools/four completions. Repeated chunk contents are sent once within the cumulative 24,000-token evidence budget.
- Query API and trace/history reads enforce workspace membership; provider IO releases database transactions; revocation is rechecked before results are persisted/returned.
- Actual provider identity, prompt version, cached/input/output tokens, tool input/output/duration, latency, quote diagnostics and dated price metadata persist in immutable query traces. Unknown pricing/usage remains explicit; reported usage on rejected completions is retained.
- Independent review found malformed nested payload handling, protocol-disconnect classification, repeated-context budget and partial-config default issues. All reproduced with regressions and fixed. Re-review approved; reviewer independently ran 40 targeted PostgreSQL tests.
- Final suite for this increment: **159 tests passing**, no skipped PostgreSQL tests; Ruff and schema checks pass.
- Native HTTP smoke with a controlled local provider verifies upload → separate worker → real pgvector → calculator loop → cited query → persisted history. This proves runtime wiring, not live model accuracy. Temporary database/server/provider removed afterward.
- Next: dataset management, immutable evaluation snapshots/execution, semantic evaluation, regression comparisons and benchmark corpus; then full frontend and release requirements. No release or remote push yet.


### Evaluation and benchmark checkpoint — 2026-09-28

- Versioned dataset management, portable export and idempotent evaluation submission implemented. Runs snapshot cases, dataset revision, query/index settings, exact corpus/vector digests and evaluator/prompt/provider identity.
- Separate worker resumes missing cases after interruption, fences every result by its lease and atomically completes aggregated observations. Changed evidence/protocol and revoked access fail explicitly; later uploads cannot enter the saved corpus.
- Metrics distinguish deterministic source/quote checks from model-estimated support. Actual evaluator embeddings supply similarity; judge claims/citations must align with observed output. Missing scores remain null with coverage; failed cases remain in operational rates.
- Comparisons require matching logical corpus/dataset and evaluator protocol. They flag quality/latency/cost regressions and refuse passing gates on incomplete cost coverage, reduced quality coverage or evaluator errors.
- Added eight original fictional policies and **60 authored benchmark cases**, including calculator/metadata, unsupported questions and adversarial text. CLI validates checksums/labels, seeds both embedding configurations, schedules experiments and exports actual persisted results/traces/comparisons.
- Independent review found lost cost coverage, stale locked dataset version and unrecorded provider changes. Regression tests reproduce/fix all three. Benchmark review caught an invalid config key and missing dataset guard; both fixed and tested. Re-review approved with no outstanding findings.
- Full suite: **185 passing tests**, with real PostgreSQL and no skips. Ruff lint/format and Alembic schema check pass; full downgrade to base and upgrade to head succeed.
- Native HTTP smoke used a temporary real database, separately launched API/worker and controlled local provider. Repeated CLI seeding reused resources; 16 documents indexed across small/large configurations; two 60-case semantic evaluations completed; all 120 results and traces exported; unknown custom-provider pricing produced an inconclusive gate. Temporary processes/database/reports removed afterward. This verifies runtime wiring, not live-model accuracy.
- Remaining: complete frontend/browser journeys, live-provider measurements and failure analysis, Docker execution, release/deployment/docs/screenshots/GIF. No remote push or deployment performed. Goal remains active.


### Research console checkpoint — 2026-09-28

- Implemented responsive Next.js console for authentication/account administration, workspace memberships/dashboard, embedding/chunk configuration, uploads/indexing, paginated documents/chunks, grounded queries, source quotes, saved history and tool/usage traces.
- Added versioned case authoring, conflict handling, dataset export, idempotent evaluation controls, asynchronous progress/results, per-case inspection, immutable configuration records and coverage-aware comparisons. Missing metrics remain unmeasured; unknown cost and incomplete provider usage stay explicit.
- Independent review reproduced and resolved incorrect upload-index field naming, dataset refresh races, incomplete token labeling, stale self-demotion controls, form pagination submission and a clean-checkout asset-directory issue. Browser testing also caught nullable queued-run metrics, mobile landmarks and footer contrast. Final re-review approved with no outstanding findings.
- Verified **185 backend tests** against real PostgreSQL 17 with no skips, Ruff lint/format and Alembic schema check. Verified production Next build, ESLint, TypeScript and Prettier. **7 Chromium browser journeys pass**, including axe checks, responsive navigation, actual pgvector ingestion/query, source inspection, agent tools/provider failure, two semantic evaluation runs, version conflict/save/reload preservation, unknown-cost comparison, RBAC/session revocation and account provisioning.
- Browser fixtures used a disposable database, separately launched API/worker and controlled HTTP provider. Temporary databases/processes were cleaned up; zero temporary browser databases remain. Fixture metrics are not live provider quality results.
- Added non-root standalone frontend image, Compose console service/configuration, CI browser/image jobs, native/HTTPS deployment documentation and five screenshots with fixture provenance. YAML definitions parse; Docker execution remains unverified because no Docker runtime is available. ESLint is pinned to the Next-compatible 9.x release used by the existing console stack; npm reports its upstream support warning.
- Remaining: live-provider benchmark measurements and failure analysis, actual container/deployment verification, published release workflow and demo GIF. No remote push or deployment performed. The overall goal remains active.


### Demo, release and container checkpoint — 2026-09-28

- Recorded a real product journey against the production Next.js frontend, API, worker
  and disposable PostgreSQL; committed the GIF, recording script and regeneration guide.
  Accounts/documents are fictional and the HTTP model provider is explicitly controlled.
  The recording is integration evidence, not a live-model quality measurement.
- Added tag-triggered GHCR publishing gated by the complete reusable CI workflow, pinned
  publishing actions, minimal job permissions, amd64/arm64 build targets, provenance/SBOM
  output, version/SHA tags and digest-based Compose deployment instructions. No tag was
  pushed and no registry publication or public deployment has been performed.
- Source review approved both media/release increments with no findings. All six action
  pins resolve; actionlint, Compose base/release configuration validation, frontend lint,
  TypeScript, Prettier and the recording journey pass.
- Built both Dockerfiles locally and started isolated Compose services with fresh database
  volumes. Alembic exited successfully; API/database readiness passed. Backend and console
  runtime images use nonroot users. **All 7 browser journeys passed (24.0s)** against
  the actual containerized app, separate worker and database on **Linux/arm64**, using the
  existing controlled provider fixture in a separate private-network container.
- The temporary verification override changed host ports, fixture provider settings and
  seeded fictional accounts; it retained the built product images and migrations. The
  initial EvalRAG container attempt exposed an incorrect fixture mount path, corrected
  before a fresh database rerun. No product code change was needed.
- Removed the disposable Compose projects/volumes and temporary runner configuration.
  Existing native PostgreSQL and the user's Podman VM were not modified. Local native
  test results from earlier checkpoints remain separate from this container verification.
- Remaining: measured live-provider benchmark reports with failure analysis, remote CI/
  registry evidence, public deployment and final PRD acceptance audit. No real-provider
  API credentials or deployment target have been supplied. Full release scope remains open.


### Acceptance mapping and portfolio documentation — 2026-09-28

- Audited the source PRD against current modules, tests, UI routes, benchmark artifacts
  and execution evidence. Added `docs/acceptance.md` with each functional requirement,
  required UI/reliability behavior, success criterion and explicit unresolved release gate.
- Embedded the architecture directly in the README, added design tradeoffs and linked
  tested failure analysis. FlowPilot now includes every allowed transition from its domain
  state model. EvalRAG explicitly distinguishes benchmark readiness from unmeasured scores.
- Reran the complete backend check script on PostgreSQL: **185 tests pass**, Ruff/format
  and schema drift checks pass. FlowPilot's 102-scenario report also passes. Documentation
  links resolve; no runtime code changed in this documentation increment.
- Confirmed both supplied GitHub repositories are empty and local Git dry-run publication
  succeeds. The connector itself has read-only access; local Git credentials provide the
  publishing route. Live-provider keys and a public hosting target remain unavailable.
- Remote CI/publication evidence is still pending at this checkpoint. Final completion
  remains unproven until the open gates in the acceptance audit are satisfied.

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

- [ ] Deliverable: `config.py, db.py, models.py, migrations`.
- [ ] Behavior evidence: Constraints reject duplicate document checksums and cross-workspace references; migrations upgrade and downgrade on PostgreSQL.
- [ ] Run the backend suite (`.venv/bin/pytest`) and relevant integration/browser checks.
- [ ] Commit the verified increment and record evidence below.

### 2. Ingestion and vector indexing

- [ ] Deliverable: `ingestion.py, providers.py, worker.py`.
- [ ] Behavior evidence: PDF/TXT/Markdown parsing preserves provenance; token overlap terminates; duplicate ingestion reuses the record; actual pgvector ranking returns expected chunks.
- [ ] Run the backend suite (`.venv/bin/pytest`) and relevant integration/browser checks.
- [ ] Commit the verified increment and record evidence below.

### 3. Grounded query and tools

- [ ] Deliverable: `rag.py, tools.py, api.py`.
- [ ] Behavior evidence: Unsupported citations and arithmetic attacks fail closed; abstention is explicit; query trace stores actual usage/latency/cost.
- [ ] Run the backend suite (`.venv/bin/pytest`) and relevant integration/browser checks.
- [ ] Commit the verified increment and record evidence below.

### 4. Evaluation and regression

- [ ] Deliverable: `evaluation.py, benchmarks/`.
- [ ] Behavior evidence: 50–100 cases with references; immutable run snapshots; known precision/recall/rank metrics; failed cases affect error rate; comparable run regression gates.
- [ ] Run the backend suite (`.venv/bin/pytest`) and relevant integration/browser checks.
- [ ] Commit the verified increment and record evidence below.

### 5. Frontend and operational delivery

- [ ] Deliverable: `frontend/, Dockerfile, compose.yaml, .github/workflows/`.
- [ ] Behavior evidence: Browser journey for ingestion/query/evaluation/comparison; responsive accessible UI; CI and builds pass; screenshots and GIF reflect real runtime.
- [ ] Run the backend suite (`.venv/bin/pytest`) and relevant integration/browser checks.
- [ ] Commit the verified increment and record evidence below.

## Evidence ledger

- 2026-09-28: Read both source PRDs, verified remote repository empty, cloned independent repository, preserved source requirements and architecture. Implementation in progress.

# PRD acceptance audit

Audited 2026-09-28 against [the source PRD](PRD.md), implementation at `d6dd87d`,
and the execution evidence in [the ledger](implementation-plan.md). This is an
acceptance map, not a claim that the final release is complete.

**Implemented** means source and scoped tests establish the stated software behavior.
**Open** means the required final evidence is absent. Controlled provider responses
cannot establish real-model quality, production reliability or public deployment.

## Functional requirements and core journeys

| PRD requirement | Implementation and direct verification | Status |
| --- | --- | --- |
| FR-1 / journey 5.1: PDF/TXT/Markdown, metadata, checksum and ingestion status | [documents](../backend/src/evalrag/documents.py), [ingestion](../backend/src/evalrag/ingestion.py); [parser, page, limit and idempotency tests](../backend/tests/test_ingestion.py); upload/source browser journey | Implemented; OCR is outside supported input |
| FR-2: fixed-token and recursive chunks, size/overlap | [chunking](../backend/src/evalrag/chunking.py), [core tests](../backend/tests/test_core.py) | Implemented; semantic chunking is stretch scope |
| FR-3: two embedding models, dimension/index version | [providers](../backend/src/evalrag/providers.py), [models](../backend/src/evalrag/models.py), [provider contract tests](../backend/tests/test_ingestion.py) | Small/large OpenAI models implemented; live measurements open |
| FR-4/5: pgvector dense top-k | [retrieval](../backend/src/evalrag/retrieval.py), [PostgreSQL ranking tests](../backend/tests/test_retrieval.py) | Implemented; hybrid/BM25/reranking are stretch scope |
| FR-6 / journey 5.2: grounded answers, citations and abstention | [RAG orchestration](../backend/src/evalrag/rag.py), [generation](../backend/src/evalrag/generation.py), [grounding/abstention tests](../backend/tests/test_rag.py), playground browser journey | Implemented; semantic validity remains estimated |
| FR-7: document search, calculator, metadata; tool input/output/timing/failure | [tools](../backend/src/evalrag/tools.py), [bounded/scoped tool tests](../backend/tests/test_rag.py) and saved trace browser journey | Implemented |
| Journey 5.3: cases with question, reference, sources, expected tools, tags and notes | [dataset API](../backend/src/evalrag/evaluation_api.py), [version/idempotency tests](../backend/tests/test_evaluation_api.py), dataset editor browser journey | Implemented |
| FR-8 / section 7: retrieval, generation, citation and operational metrics | [evaluation](../backend/src/evalrag/evaluation.py), [semantic evaluation](../backend/src/evalrag/semantic_evaluation.py), [metric tests](../backend/tests/test_evaluation.py), [semantic protocol tests](../backend/tests/test_semantic_evaluation.py) | Implemented; live scores open |
| FR-9 / journey 5.4: immutable experiments, configuration selection and regression comparison | [evaluation worker](../backend/src/evalrag/evaluation_worker.py), [snapshot/resumption tests](../backend/tests/test_evaluation_worker.py), coverage and changed-input comparison tests; comparison browser journey | Implemented; two completed live runs open |
| FR-10: request/model/prompt/retrieval/error/latency/token/cost provenance | [query API](../backend/src/evalrag/query_api.py), [RAG trace tests](../backend/tests/test_rag.py), [pricing tests](../backend/tests/test_pricing.py) | Implemented; unknown usage/pricing remain explicit |

## UI, architecture and reliability

- All five required surfaces exist under [the console routes](../frontend/src/app/%28console%29):
  dashboard, knowledge bases, playground, dataset/evaluation editor and comparison.
  [Seven browser journeys](../frontend/tests/console.spec.ts) cover the complete flow,
  responsive navigation, accessibility, conflicts, role enforcement and failure display.
- FastAPI, Next.js/TypeScript, PostgreSQL/pgvector and separate durable workers implement
  the required architecture. [Models](../backend/src/evalrag/models.py) and Alembic
  migrations persist all PRD entities plus session, membership, trace and job records.
- [Persistence](../backend/tests/test_persistence.py), [jobs](../backend/tests/test_jobs.py),
  [worker](../backend/tests/test_worker.py), [auth](../backend/tests/test_auth.py) and
  domain/API tests cover transactions, lease fencing, reproducibility, idempotent ingestion,
  structured provider failure and deterministic citation checks. The last full native run
  passed 185 tests with actual PostgreSQL; no database behavior is inferred from SQLite.
- Both nonroot Dockerfiles built on Linux/arm64. All seven browser journeys passed against
  containerized API, worker, PostgreSQL/pgvector and standalone frontend. This does not
  prove amd64 runtime, real provider behavior, load capacity or public HTTPS deployment.
- [CI](../.github/workflows/ci.yml) runs on every pull request and main push, checks schema
  roundtrips and builds both images. [Release](../.github/workflows/release.yml) calls all CI
  gates before publishing versioned images. Remote execution evidence is still open.

## Success criteria and final gates

| PRD success criterion / milestone | Evidence | Acceptance |
| --- | --- | --- |
| 50–100 questions | [60-case dataset](../benchmarks/dataset.json), [checksummed manifest](../benchmarks/manifest.json), [bundle tests](../backend/tests/test_benchmark.py) | Implemented |
| Two retrieval configurations and prompt/model changes compared | Configured benchmark commands plus comparison/API/browser tests | Software implemented; measured live comparison open |
| Citation coverage and unsupported claims visible | Evaluation summary and case detail in browser suite / [screenshots](screenshots/README.md) | Implemented |
| p95 latency and estimated cost | Persisted run metrics and comparison view; missing coverage tested | Implemented; live operational table open |
| README diagram, screenshots, demo GIF | Embedded README diagrams and images; [recording provenance](demo.md) | Present |
| README benchmark table and failure analysis | Readiness table, [method](../benchmarks/README.md), [failure analysis](failure-analysis.md) | Measured benchmark table open; do not substitute fixture scores |
| Deployment and portfolio launch | Local container execution and deployment runbook | Public deployment, remote CI/image publication and final release open |

Required next evidence: configured provider credentials; two complete live benchmark runs
with provenance, coverage and inspected failures; successful remote CI and image publication;
chosen hosting target and a verified deployed journey. No final completion claim is justified yet.

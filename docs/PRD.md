# Source PRD

Extracted verbatim from the supplied Word document; table cells are separate paragraphs.

EvalRAG

Production RAG + Agent Evaluation Platform

Portfolio-grade product requirements document



1. Executive Summary

EvalRAG is a production-style platform for building, testing, and evaluating retrieval-augmented generation and agentic AI systems. It combines document ingestion, configurable retrieval, grounded Q&A with citations, agent/tool execution, automated evaluation, regression testing, latency/cost tracking, and observability in one system.

The product is intentionally designed to go beyond a basic chatbot. Its differentiator is measurable reliability: every change to prompts, embeddings, retrieval settings, or models can be evaluated against a repeatable benchmark.

2. Product Goals

Create and manage document-backed knowledge bases.

Ask grounded questions with traceable citations.

Compare retrieval and generation configurations.

Evaluate RAG quality using automated benchmark datasets.

Detect regressions before deployment.

Track operational metrics such as latency, token usage, and estimated cost.

Inspect failures at the retrieval, generation, citation, and tool-execution layers.

Expose the core system through clean APIs and a usable web interface.

3. Non-Goals

Training or fine-tuning foundation models in v1.

Building a proprietary vector database.

Enterprise SSO, billing, or multi-region architecture.

Supporting every LLM provider or document format.

Creating a general-purpose agent marketplace.

4. Target Users

Field

Details

AI / ML Engineer

Builds and tunes retrieval pipelines, evaluates quality, and investigates regressions.

Software Engineer

Integrates the service into applications, manages APIs, deployments, and observability.

Product / QA Reviewer

Creates evaluation cases, reviews outputs, and validates citations and failure modes.

5. Core User Journeys

5.1 Create a Knowledge Base

Create a workspace and knowledge base.

Upload PDF, TXT, or Markdown documents.

Extract text and metadata.

Chunk content using the selected strategy.

Generate embeddings.

Index vectors.

Display ingestion summary, chunk count, failures, model version, and duration.

5.2 Ask a Grounded Question

User submits a natural-language question.

System embeds the query.

Retriever selects top-k candidate chunks.

Optional reranker reorders candidates.

Generation service constructs a grounded prompt.

LLM generates an answer.

Citation validator checks source support.

UI returns the answer, citations, retrieved context, scores, latency, and token usage.

5.3 Build an Evaluation Dataset

Each evaluation case should support:

Question

Expected answer or reference answer

Expected source(s)

Expected tool call, when applicable

Tags such as retrieval, citation, difficult, or adversarial

Optional human notes

5.4 Run and Compare Evaluations

Users select a model, prompt version, embedding model, retriever, top-k, and optional reranker. Each run is stored as an immutable experiment and can be compared to a baseline.

Metric

Baseline

Candidate

Change

Precision@5

0.81

0.89

+0.08

Citation coverage

91%

98%

+7 pp

Average latency

1.6 s

1.9 s

+0.3 s

Estimated cost / query

$0.011

$0.009

-18%

6. Functional Requirements

FR-1 Document Ingestion

Support PDF, TXT, and Markdown. Preserve filename, page/section metadata, checksums, ingestion status, and failure details.

FR-2 Chunking

Support fixed-token and recursive chunking with configurable chunk size and overlap. Semantic chunking is a stretch goal.

FR-3 Embeddings

Support at least two embedding providers/models and record model name, dimension, and index version.

FR-4 Vector Search

Use Postgres + pgvector for v1. Support configurable top-k dense retrieval.

FR-5 Retrieval

Dense retrieval required; BM25, hybrid retrieval, and reranking are stretch goals.

FR-6 Grounded Generation

Responses must use retrieved context, include citations, return structured metadata, and abstain when evidence is insufficient.

FR-7 Agent Tools

Include safe tools such as document search, calculator, and metadata lookup. Log tool input, output, duration, and failure state.

FR-8 Evaluation Engine

Compute retrieval, generation, citation, and operational metrics.

FR-9 Regression Testing

Compare candidate runs with baselines and flag material quality regressions.

FR-10 Observability

Persist request IDs, model/prompt versions, retrieved chunks, latency, token usage, cost estimates, and errors.

7. Evaluation Metrics

Field

Details

Retrieval

Precision@k, Recall@k, Hit Rate, optional MRR

Generation

Exact match where applicable, semantic similarity, groundedness, answer relevance

Citations

Citation coverage, citation correctness, unsupported-claim rate

Operational

p50/p95 latency, input/output tokens, estimated cost, error rate

8. Technical Architecture

Recommended architecture: Next.js frontend -> FastAPI backend -> RAG service + evaluation service -> Postgres/pgvector + object storage. LLM and embedding providers should sit behind provider abstractions so experiments can switch implementations without changing product code.

9. Suggested Tech Stack

Field

Details

Frontend

Next.js, React, TypeScript, Tailwind

Backend

Python, FastAPI, Pydantic

Database

Postgres + pgvector

AI

OpenAI or Anthropic; sentence-transformers; optional LangGraph

Infrastructure

Docker, GitHub Actions, Render/Railway/Fly.io/AWS

Observability

Structured logging; optional OpenTelemetry

10. Data Model

Field

Details

workspaces

id, name, created_at

knowledge_bases

id, workspace_id, name, embedding_model, chunk_strategy, created_at

documents

id, knowledge_base_id, filename, checksum, status, created_at

chunks

id, document_id, content, metadata, embedding

evaluation_cases

id, question, expected_answer, expected_sources, tags

evaluation_runs

id, config, started_at, completed_at

evaluation_results

run_id, case_id, answer, retrieved_chunks, metrics, latency, cost

11. Required UI

Dashboard: knowledge bases, evaluation runs, and recent activity.

Knowledge Base: documents, ingestion status, chunk statistics, and configuration.

Playground: question input, answer, citations, retrieved context, latency, and cost.

Evaluations: dataset editor, run controls, metric summaries, and failures.

Compare: baseline-vs-candidate metrics, regressions, and improvements.

12. Reliability & Quality Requirements

Core backend logic covered by unit and integration tests.

Evaluation runs must be reproducible from saved configuration.

Document ingestion must be idempotent using checksums.

Provider errors must return structured failure states.

Citation validation must be deterministic where possible.

CI must run tests on every pull request.

13. Success Criteria

Benchmark dataset contains at least 50-100 evaluation questions.

At least two retrieval configurations can be compared.

Citation coverage and unsupported-claim rate are visible in the UI.

Regression comparison works across prompt/model/retrieval versions.

Operational metrics include p95 latency and estimated cost.

Architecture diagram, screenshots, demo GIF, and benchmark table are included in the README.

14. Milestones

Document ingestion + pgvector indexing

Grounded Q&A + citations

Evaluation dataset + metric engine

Regression comparison

Agent/tool calling

Observability + cost tracking

Frontend polish + deployment

README, demo, benchmarks, and portfolio launch

15. Portfolio Narrative

The project should communicate: “I know how to make RAG and agent systems measurable, testable, and safe to iterate.” The README should emphasize engineering decisions, evaluation methodology, failure analysis, and tradeoffs rather than just features.

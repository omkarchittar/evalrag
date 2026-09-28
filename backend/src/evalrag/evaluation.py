"""Fixed experiment inputs and transparent deterministic/operational metrics."""

import hashlib
import json
from dataclasses import asdict
from statistics import mean

from sqlalchemy import func, select

from evalrag.metrics import aggregate_operations, compare_metrics, exact_match, retrieval_metrics
from evalrag.models import (
    Chunk,
    Document,
    EvaluationCase,
    EvaluationDataset,
    EvaluationRun,
    Job,
    KnowledgeBase,
)
from evalrag.rag import PROMPTS, SYSTEM, QueryConfig
from evalrag.retrieval import IndexSpec
from evalrag.semantic_evaluation import judge_fingerprint

CASE_FIELDS = [
    "id",
    "question",
    "expected_answer",
    "expected_sources",
    "expected_abstention",
    "expected_tool",
    "tags",
    "notes",
]
QUALITY = [
    "precision_at_k",
    "recall_at_k",
    "hit_rate",
    "mrr",
    "exact_match",
    "abstention_accuracy",
    "tool_accuracy",
    "citation_coverage",
    "quote_correctness",
    "citation_correctness",
    "semantic_similarity",
    "groundedness",
    "answer_relevance",
    "unsupported_claim_rate",
]
JUDGE_VERSION = "judge-v1"


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def prompt_hash(config: QueryConfig):
    return digest(SYSTEM + "\n" + PROMPTS[config.prompt_version])


def corpus_manifest(db, kb_id, *, document_ids=None):
    query = select(Document).where(Document.knowledge_base_id == kb_id, Document.status == "ready")
    if document_ids is not None:
        query = query.where(Document.id.in_(document_ids))
    docs = db.scalars(query.order_by(Document.id).limit(1001)).all()
    if len(docs) > 1000:
        raise ValueError("Evaluation corpus exceeds 1000 documents")
    manifest = []
    total = 0
    for doc in docs:
        count = db.scalar(
            select(func.count()).select_from(Chunk).where(Chunk.document_id == doc.id)
        )
        total += count
        if total > 20_000:
            raise ValueError("Evaluation corpus exceeds 20000 chunks")
        hasher = hashlib.sha256()
        rows = db.execute(
            select(
                Chunk.id,
                Chunk.ordinal,
                Chunk.page,
                Chunk.content,
                Chunk.token_count,
                Chunk.embedding,
                Chunk.embedding_dimension,
                Chunk.index_version,
            )
            .where(Chunk.document_id == doc.id)
            .order_by(Chunk.ordinal)
            .execution_options(yield_per=100)
        )
        for row in rows:
            values = list(row)
            values[5] = [float(value) for value in values[5]]
            hasher.update(
                json.dumps(
                    values, ensure_ascii=False, separators=(",", ":"), allow_nan=False
                ).encode()
            )
            hasher.update(b"\n")
        manifest.append(
            {
                "id": doc.id,
                "checksum": doc.checksum,
                "filename": doc.filename,
                "chunk_count": count,
                "index_hash": hasher.hexdigest(),
            }
        )
    return manifest


def build_run(
    db,
    *,
    dataset_id,
    kb_id,
    name,
    query: QueryConfig,
    evaluate_semantics: bool,
    evaluator_model: str | None,
    provider_identity: str,
    requested_by: str | None = None,
    job_key: str | None = None,
    submission_hash: str | None = None,
):
    dataset = db.scalar(
        select(EvaluationDataset)
        .where(EvaluationDataset.id == dataset_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    kb = db.get(KnowledgeBase, kb_id)
    if dataset is None or kb is None or dataset.workspace_id != kb.workspace_id:
        raise ValueError("Dataset and knowledge base must share a workspace")
    cases = db.scalars(
        select(EvaluationCase)
        .where(EvaluationCase.dataset_id == dataset.id)
        .order_by(EvaluationCase.id)
        .limit(201)
    ).all()
    if not 1 <= len(cases) <= 200:
        raise ValueError("Evaluation datasets must contain 1–200 cases")
    corpus = corpus_manifest(db, kb_id)
    if not corpus or not any(d["chunk_count"] for d in corpus):
        raise ValueError("Knowledge base has no ready indexed documents")
    snapshot = [{key: getattr(case, key) for key in CASE_FIELDS} for case in cases]
    logical_cases = sorted(
        [{key: value for key, value in case.items() if key != "id"} for case in snapshot],
        key=digest,
    )
    logical_corpus = sorted(
        [{"checksum": d["checksum"], "filename": d["filename"]} for d in corpus], key=digest
    )
    config = {
        "requested_by": requested_by,
        "provider_identity": provider_identity,
        "submission_hash": submission_hash,
        "query": query.model_dump(),
        "index": asdict(IndexSpec.from_kb(kb)),
        "dataset_version": dataset.version,
        "prompt_hash": prompt_hash(query),
        "evaluate_semantics": evaluate_semantics,
        "evaluator_model": evaluator_model if evaluate_semantics else None,
        "judge_version": JUDGE_VERSION,
        "judge_fingerprint": judge_fingerprint(),
        "evaluator_embedding_model": "text-embedding-3-small",
        "evaluator_embedding_dimension": 1536,
    }
    row = EvaluationRun(
        workspace_id=dataset.workspace_id,
        dataset_id=dataset.id,
        knowledge_base_id=kb.id,
        name=name,
        config=config,
        dataset_snapshot=snapshot,
        corpus_snapshot=corpus,
        dataset_hash=digest(logical_cases),
        corpus_hash=digest(logical_corpus),
    )
    db.add(row)
    db.flush()
    db.add(
        Job(
            kind="evaluate_run",
            resource_id=row.id,
            idempotency_key=job_key or f"evaluate:{row.id}",
            payload={},
        )
    )
    db.flush()
    return row


def score_trace(trace, case, corpus, *, top_k):
    checksums = {d["id"]: d["checksum"] for d in corpus}
    # Retrieval metrics measure the initial top-k ranking; later agent searches
    # remain in the trace but must not inflate initial retriever recall.
    sources = {s["chunk_id"]: s["document_id"] for s in trace.retrieved}
    searches = trace.config.get("retrievals", [])
    ranked = searches[0]["ranked_chunk_ids"] if searches else []
    retrieved = [
        checksums[sources[key]] for key in ranked if key in sources and sources[key] in checksums
    ]
    scores = retrieval_metrics(retrieved, case["expected_sources"], k=top_k)
    expected_tool = case.get("expected_tool")
    expected_abstention = case.get("expected_abstention")
    valid = trace.config.get("answer_validation", {})
    scores.update(
        exact_match=exact_match(trace.answer or "", case.get("expected_answer")),
        abstention_accuracy=None
        if expected_abstention is None
        else float(not trace.error_code and trace.abstained == expected_abstention),
        tool_accuracy=None
        if expected_tool is None
        else float(
            any(t["name"] == expected_tool and t["status"] == "success" for t in trace.tool_calls)
        ),
        citation_coverage=valid.get("citation_coverage"),
        quote_correctness=valid.get("citation_correctness"),
        citation_correctness=None,
        semantic_similarity=None,
        groundedness=None,
        answer_relevance=None,
        unsupported_claim_rate=None,
        evaluation_error=None,
        evaluator_usage=[],
    )
    return scores


def aggregate_results(rows):
    # rows contain (case metrics, immutable trace); missing labels/scores stay null.
    quality = {}
    coverage = {}
    for key in QUALITY:
        values = [metrics[key] for metrics, _ in rows if metrics.get(key) is not None]
        quality[key] = mean(values) if values else None
        coverage[key] = len(values) / len(rows) if rows else None
    operations = aggregate_operations(
        [
            {
                "latency_ms": t.latency_ms,
                "input_tokens": t.input_tokens,
                "output_tokens": t.output_tokens,
                "cost_usd": t.cost_usd,
                "error": t.error_code,
            }
            for _, t in rows
        ]
    )
    evaluator_usage = [entry for metrics, _ in rows for entry in metrics.get("evaluator_usage", [])]
    evaluator_cost = (
        None
        if any(m.get("evaluation_error") for m, _ in rows)
        or any(u["cost_usd"] is None for u in evaluator_usage)
        else sum(u["cost_usd"] for u in evaluator_usage)
    )
    return {
        "quality": quality,
        "coverage": coverage,
        "operations": operations,
        "case_count": len(rows),
        "failed_cases": sum(bool(t.error_code) for _, t in rows),
        "abstention_rate": mean(t.abstained for _, t in rows) if rows else None,
        "evaluation_error_rate": mean(bool(m.get("evaluation_error")) for m, _ in rows)
        if rows
        else None,
        "evaluator": {
            "input_tokens": sum(u["input_tokens"] for u in evaluator_usage),
            "output_tokens": sum(u["output_tokens"] for u in evaluator_usage),
            "cost_usd": evaluator_cost,
            "models": sorted({u["model"] for u in evaluator_usage if u["kind"] == "generation"}),
        },
    }


def compare_runs(baseline, candidate, *, quality_tolerance=0.05, operational_tolerance=0.2):
    if (
        baseline.workspace_id != candidate.workspace_id
        or baseline.status != "completed"
        or candidate.status != "completed"
    ):
        raise ValueError("Only completed runs from the same workspace may be compared")
    if (
        baseline.dataset_hash != candidate.dataset_hash
        or baseline.corpus_hash != candidate.corpus_hash
    ):
        raise ValueError("Dataset or corpus identity differs")
    fields = [
        "provider_identity",
        "evaluate_semantics",
        "evaluator_model",
        "judge_version",
        "evaluator_embedding_model",
        "evaluator_embedding_dimension",
        "judge_fingerprint",
    ]
    if any(baseline.config.get(k) != candidate.config.get(k) for k in fields):
        raise ValueError("Evaluation protocols differ")
    before, after = baseline.metrics, candidate.metrics
    actual_before = before.get("evaluator", {}).get("models", [])
    actual_after = after.get("evaluator", {}).get("models", [])
    if actual_before != actual_after:
        raise ValueError("Observed evaluator models differ")
    comparisons = compare_metrics(
        {**before["quality"], **before["operations"]},
        {**after["quality"], **after["operations"]},
        quality_tolerance=quality_tolerance,
        operational_tolerance=operational_tolerance,
    )
    missing = [
        k
        for k, v in before["quality"].items()
        if v is not None
        and (
            after["quality"].get(k) is None
            or (after["coverage"].get(k) or 0) < (before["coverage"].get(k) or 0)
        )
    ]
    missing.extend(
        row["metric"]
        for row in comparisons
        if row["metric"] in before["operations"]
        and row["baseline"] is not None
        and row["candidate"] is None
    )
    if any(
        operations.get("cost_coverage") is not None and operations["cost_coverage"] < 1
        for operations in (before["operations"], after["operations"])
    ):
        missing.append("cost_coverage")
    inconclusive = bool(
        missing
        or before.get("evaluation_error_rate")
        or after.get("evaluation_error_rate")
        or not any(c["delta"] is not None for c in comparisons)
    )
    regression = any(row["regression"] is True for row in comparisons)
    return {
        "baseline_id": baseline.id,
        "candidate_id": candidate.id,
        "metrics": comparisons,
        "coverage": {
            "quality": {"baseline": before["coverage"], "candidate": after["coverage"]},
            "operations": {
                "baseline_cost": before["operations"].get("cost_coverage"),
                "candidate_cost": after["operations"].get("cost_coverage"),
            },
        },
        "regression": regression,
        "inconclusive": inconclusive,
        "missing_or_reduced_coverage": missing,
        "passed": not regression and not inconclusive,
        "thresholds": {
            "quality_absolute": quality_tolerance,
            "operational_relative": operational_tolerance,
        },
    }

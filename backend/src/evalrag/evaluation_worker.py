"""Resumable evaluation processing; commit each observation under current ownership."""

from sqlalchemy import select

from evalrag.db import utcnow
from evalrag.evaluation import (
    JUDGE_VERSION,
    aggregate_results,
    corpus_manifest,
    prompt_hash,
    score_trace,
)
from evalrag.jobs import assert_owned, complete
from evalrag.models import EvaluationResult, EvaluationRun, QueryTrace
from evalrag.providers import ProviderError
from evalrag.rag import QueryAccessError, QueryConfig, accessible_index, ask
from evalrag.retrieval import IndexSpec
from evalrag.semantic_evaluation import evaluate_semantics, judge_fingerprint


def locked_run(db, identifier):
    row = db.scalar(
        select(EvaluationRun)
        .where(EvaluationRun.id == identifier)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise ProviderError("evaluation_not_found")
    return row


def verify_inputs(db, run, providers):
    if run.config.get("provider_identity") != providers.identity:
        raise ProviderError("evaluation_protocol_changed")
    config = QueryConfig(**run.config["query"])
    expected = IndexSpec(**run.config["index"])
    try:
        actual = accessible_index(db, run.knowledge_base_id, run.config.get("requested_by"))
    except QueryAccessError as exc:
        raise ProviderError("evaluation_access_revoked") from exc
    if actual != expected or prompt_hash(config) != run.config["prompt_hash"]:
        raise ProviderError("evaluation_configuration_changed")
    if (
        run.config["judge_version"] != JUDGE_VERSION
        or run.config.get("judge_fingerprint") != judge_fingerprint()
    ):
        raise ProviderError("evaluation_protocol_changed")
    ids = [d["id"] for d in run.corpus_snapshot]
    if corpus_manifest(db, run.knowledge_base_id, document_ids=ids) != run.corpus_snapshot:
        raise ProviderError("evaluation_corpus_changed")


def process_evaluation(database, lease, providers):
    with database.transaction() as db:
        assert_owned(db, lease)
        run = locked_run(db, lease.resource_id)
        if run.status in {"completed", "failed"}:
            complete(db, lease)
            return
        verify_inputs(db, run, providers)
        run.status = "running"
        run.error_code = None
        run.started_at = run.started_at or utcnow()
        config = QueryConfig(**run.config["query"])
        # Stored JSON values and dataclasses remain usable after this short transaction.
        cases = run.dataset_snapshot
        corpus = run.corpus_snapshot
        run_config = run.config
        kb_id = run.knowledge_base_id
    for case in cases:
        with database.transaction() as db:
            assert_owned(db, lease)
            done = db.scalar(
                select(EvaluationResult.id).where(
                    EvaluationResult.run_id == lease.resource_id,
                    EvaluationResult.case_id == case["id"],
                )
            )
            if done:
                continue
        try:
            trace = ask(
                database,
                kb_id,
                actor_id=run_config.get("requested_by"),
                question=case["question"],
                config=config,
                request_id=f"eval_{lease.resource_id}_{case['id']}",
                embedding_factory=providers.embedding,
                generation_factory=providers.generation,
                document_ids=[d["id"] for d in corpus],
                standard_openai=providers.standard_openai,
            )
        except QueryAccessError as exc:
            raise ProviderError("evaluation_access_revoked") from exc
        metrics = score_trace(trace, case, corpus, top_k=config.top_k)
        if run_config["evaluate_semantics"] and trace.answer and not trace.error_code:
            try:
                evaluator_index = IndexSpec(
                    kb_id,
                    run_config["index"]["workspace_id"],
                    run_config["evaluator_embedding_model"],
                    run_config["evaluator_embedding_dimension"],
                    1,
                )
                metrics.update(
                    evaluate_semantics(
                        trace,
                        case,
                        embedding_provider=providers.embedding(evaluator_index),
                        judge_provider=providers.generation(run_config["evaluator_model"]),
                        standard_openai=providers.standard_openai,
                    )
                )
            except ProviderError as exc:
                metrics["evaluation_error"] = exc.code
        with database.transaction() as db:
            assert_owned(db, lease)
            db.add(
                EvaluationResult(
                    run_id=lease.resource_id, case_id=case["id"], trace_id=trace.id, metrics=metrics
                )
            )
            db.flush()
    with database.transaction() as db:
        assert_owned(db, lease)
        run = locked_run(db, lease.resource_id)
        verify_inputs(db, run, providers)
        rows = db.execute(
            select(EvaluationResult.metrics, QueryTrace)
            .join(QueryTrace, QueryTrace.id == EvaluationResult.trace_id)
            .where(EvaluationResult.run_id == run.id)
        ).all()
        if len(rows) != len(run.dataset_snapshot):
            raise ProviderError("evaluation_results_incomplete")
        run.metrics = aggregate_results(rows)
        run.status = "completed"
        run.completed_at = utcnow()
        complete(db, lease)

from copy import deepcopy

import pytest
from sqlalchemy import select
from test_persistence import knowledge_base
from test_retrieval import populate

from evalrag.evaluation import build_run, compare_runs, corpus_manifest, score_trace
from evalrag.models import EvaluationCase, EvaluationDataset, EvaluationRun, Job, QueryTrace
from evalrag.rag import QueryConfig

pytestmark = pytest.mark.postgres


def dataset(db, kb):
    row = EvaluationDataset(workspace_id=kb.workspace_id, name="Policies")
    db.add(row)
    db.flush()
    case = EvaluationCase(
        dataset_id=row.id,
        question="Retention?",
        expected_answer="Retention is 30 days.",
        expected_sources=["a" * 64],
        expected_abstention=False,
        expected_tool=None,
        tags=["policy"],
    )
    db.add(case)
    db.flush()
    return row, case


def test_run_snapshots_inputs_and_enqueues_atomically(db):
    kb = knowledge_base(db)
    populate(db, kb, [1, 0, 0])
    data, case = dataset(db, kb)
    run = build_run(
        db,
        provider_identity="test-provider",
        dataset_id=data.id,
        kb_id=kb.id,
        name="Baseline",
        query=QueryConfig(),
        evaluate_semantics=True,
        evaluator_model="gpt-4.1-mini",
    )
    original = deepcopy(run.dataset_snapshot)
    case.question = "Changed later"
    data.version += 1
    db.flush()
    assert run.dataset_snapshot == original
    assert run.config["dataset_version"] == 1
    assert run.corpus_snapshot[0]["checksum"] == "a" * 64
    assert len(run.corpus_snapshot[0]["index_hash"]) == 64
    assert db.scalar(select(Job).where(Job.resource_id == run.id)).kind == "evaluate_run"


def test_corpus_digest_catches_chunk_mutation_but_ignores_later_new_documents(db):
    kb = knowledge_base(db)
    doc, chunk = populate(db, kb, [1, 0, 0])
    first = corpus_manifest(db, kb.id)
    chunk.content = "Changed evidence"
    db.flush()
    assert corpus_manifest(db, kb.id) != first
    assert corpus_manifest(db, kb.id, document_ids=[]) == []


def test_run_rejects_cross_workspace_or_empty_inputs(db):
    kb = knowledge_base(db)
    other = knowledge_base(db)
    data, _ = dataset(db, kb)
    with pytest.raises(ValueError):
        build_run(
            db,
            provider_identity="test-provider",
            dataset_id=data.id,
            kb_id=other.id,
            name="No",
            query=QueryConfig(),
            evaluate_semantics=False,
            evaluator_model=None,
        )
    with pytest.raises(ValueError):
        build_run(
            db,
            provider_identity="test-provider",
            dataset_id=data.id,
            kb_id=kb.id,
            name="Empty",
            query=QueryConfig(),
            evaluate_semantics=False,
            evaluator_model=None,
        )


def test_case_scoring_uses_stable_document_checksums_and_explicit_ground_truth():
    trace = QueryTrace(
        answer="Retention is 30 days.",
        abstained=False,
        error_code=None,
        retrieved=[{"document_id": "doc-1"}],
        tool_calls=[],
        citations=[{"valid": True}],
        config={
            "answer_validation": {"citation_coverage": 1, "citation_correctness": 1},
            "retrievals": [{"ranked_chunk_ids": ["chunk-1"]}],
        },
    )
    trace.retrieved[0]["chunk_id"] = "chunk-1"
    case = {
        "expected_answer": "Retention is 30 days.",
        "expected_sources": ["a" * 64],
        "expected_tool": None,
        "expected_abstention": False,
    }
    scores = score_trace(trace, case, [{"id": "doc-1", "checksum": "a" * 64}], top_k=5)
    assert scores["exact_match"] == 1
    assert scores["recall_at_k"] == 1 and scores["precision_at_k"] == 0.2
    assert scores["abstention_accuracy"] == 1
    assert scores["tool_accuracy"] is None
    assert scores["quote_correctness"] == 1
    assert scores["citation_correctness"] is None  # semantic support isn't quote membership


def test_failed_cases_do_not_disappear_from_exact_match():
    trace = QueryTrace(
        answer=None,
        abstained=True,
        error_code="provider_unavailable",
        retrieved=[],
        citations=[],
        tool_calls=[],
        config={},
    )
    scores = score_trace(
        trace,
        {
            "expected_answer": "Expected",
            "expected_sources": ["a" * 64],
            "expected_tool": "calculator",
            "expected_abstention": False,
        },
        [],
        top_k=5,
    )
    assert scores["exact_match"] == 0 and scores["tool_accuracy"] == 0
    assert scores["recall_at_k"] == 0 and scores["abstention_accuracy"] == 0


def test_comparison_refuses_changed_inputs_and_flags_quality_regression():
    fields = {
        "workspace_id": "w",
        "status": "completed",
        "dataset_hash": "a",
        "corpus_hash": "b",
        "config": {
            "evaluate_semantics": False,
            "evaluator_model": None,
            "judge_version": "judge-v1",
        },
        "metrics": {
            "quality": {"exact_match": 0.9},
            "operations": {"error_rate": 0},
            "coverage": {"exact_match": 1},
            "evaluation_error_rate": 0,
        },
    }
    baseline = EvaluationRun(id="baseline", **deepcopy(fields))
    candidate = EvaluationRun(id="candidate", **deepcopy(fields))
    candidate.metrics["quality"]["exact_match"] = 0.7
    result = compare_runs(baseline, candidate)
    assert result["regression"] is True
    candidate.corpus_hash = "different"
    with pytest.raises(ValueError):
        compare_runs(baseline, candidate)


def test_locked_dataset_refreshes_version_before_snapshot(db):
    from sqlalchemy import text

    kb = knowledge_base(db)
    populate(db, kb, [1, 0, 0])
    data, _ = dataset(db, kb)
    db.execute(text("UPDATE evaluation_datasets SET version = 2 WHERE id = :id"), {"id": data.id})
    assert data.version == 1  # identity-map value from before a concurrent commit
    run = build_run(
        db,
        provider_identity="test-provider",
        dataset_id=data.id,
        kb_id=kb.id,
        name="Fresh provenance",
        query=QueryConfig(),
        evaluate_semantics=False,
        evaluator_model=None,
    )
    assert run.config["dataset_version"] == 2


@pytest.mark.parametrize("candidate_cost,candidate_coverage", [(None, 0), (0.01, 0.5)])
def test_lost_operational_coverage_cannot_pass(candidate_cost, candidate_coverage):
    fields = dict(
        workspace_id="w",
        status="completed",
        dataset_hash="a",
        corpus_hash="b",
        config={},
        metrics={
            "quality": {"exact_match": 1},
            "coverage": {"exact_match": 1},
            "operations": {"error_rate": 0, "mean_cost_usd": 0.01, "cost_coverage": 1},
        },
    )
    baseline = EvaluationRun(id="baseline", **deepcopy(fields))
    candidate = EvaluationRun(id="candidate", **deepcopy(fields))
    candidate.metrics["operations"].update(
        mean_cost_usd=candidate_cost, cost_coverage=candidate_coverage
    )
    result = compare_runs(baseline, candidate)
    assert result["inconclusive"] and not result["passed"]
    assert "cost_coverage" in result["missing_or_reduced_coverage"]
    assert result["coverage"]["operations"]["candidate_cost"] == candidate_coverage


def test_comparison_rejects_provider_protocol_change():
    fields = dict(
        workspace_id="w", status="completed", dataset_hash="a", corpus_hash="b", metrics={}
    )
    baseline = EvaluationRun(id="b", config={"provider_identity": "first"}, **fields)
    candidate = EvaluationRun(id="c", config={"provider_identity": "second"}, **fields)
    with pytest.raises(ValueError, match="protocols differ"):
        compare_runs(baseline, candidate)

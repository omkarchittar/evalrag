import pytest

from evalrag.chunking import chunk_pages
from evalrag.metrics import aggregate_operations, compare_metrics, retrieval_metrics
from evalrag.tools import calculate, validate_citations


def test_retrieval_scores_unique_source_ranking():
    result = retrieval_metrics(["a", "a", "b", "c"], ["b", "d"], k=3)
    assert result == {"precision_at_k": 1 / 3, "recall_at_k": 0.5, "hit_rate": 1.0, "mrr": 0.5}


def test_empty_retrieval_is_failure_when_sources_expected():
    assert retrieval_metrics([], ["a"], k=5) == {
        "precision_at_k": 0,
        "recall_at_k": 0,
        "hit_rate": 0,
        "mrr": 0,
    }


def test_missing_ground_truth_is_not_perfect_score():
    assert all(v is None for v in retrieval_metrics(["a"], [], k=5).values())


@pytest.mark.parametrize("k", [0, -1, 101])
def test_invalid_metric_depth(k):
    with pytest.raises(ValueError):
        retrieval_metrics(["a"], ["a"], k=k)


def test_operational_metrics_include_errors_and_interpolated_tail_latency():
    rows = [
        {
            "latency_ms": x,
            "input_tokens": 10,
            "output_tokens": 5,
            "cost_usd": 0.01,
            "error": x == 50,
        }
        for x in [10, 20, 30, 40, 50]
    ]
    metrics = aggregate_operations(rows)
    assert metrics["p50_latency_ms"] == 30
    assert metrics["p95_latency_ms"] == 48
    assert metrics["error_rate"] == 0.2
    assert metrics["total_cost_usd"] == pytest.approx(0.05)


def test_empty_operations_return_null_not_nan():
    result = aggregate_operations([])
    assert result["p95_latency_ms"] is None
    assert result["error_rate"] is None
    assert result["total_cost_usd"] == 0


def test_regression_direction_accounts_for_latency_and_quality():
    result = compare_metrics(
        {"recall_at_k": 0.8, "p95_latency_ms": 100},
        {"recall_at_k": 0.6, "p95_latency_ms": 150},
        quality_tolerance=0.05,
        operational_tolerance=0.2,
    )
    assert {r["metric"] for r in result if r["regression"]} == {"recall_at_k", "p95_latency_ms"}


@pytest.mark.parametrize("strategy", ["fixed", "recursive"])
def test_chunking_preserves_page_and_bounds(strategy):
    chunks = chunk_pages(
        [(1, "alpha beta gamma. " * 100), (2, "Second page evidence.")],
        size=32,
        overlap=8,
        strategy=strategy,
    )
    assert len(chunks) > 2
    assert all(0 < c.token_count <= 32 for c in chunks)
    assert chunks[-1].page == 2
    assert chunks[-1].content == "Second page evidence."
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))


@pytest.mark.parametrize("size,overlap", [(0, 0), (32, 32), (32, -1), (32, 100)])
def test_invalid_chunk_settings_cannot_infinite_loop(size, overlap):
    with pytest.raises(ValueError):
        chunk_pages([(1, "text")], size=size, overlap=overlap)


def test_unicode_chunking_does_not_introduce_replacement_characters():
    chunks = chunk_pages([(1, "世界🌍 café " * 100)], size=17, overlap=3)
    assert all("\ufffd" not in c.content for c in chunks)


def test_empty_documents_produce_no_chunks():
    assert chunk_pages([(1, "  \n")], size=32, overlap=8) == []


@pytest.mark.parametrize(
    "expression,expected", [("2+3*4", 14), ("(10-2)/4", 2), ("-5+2", -3), ("2**8", 256)]
)
def test_calculator_valid_arithmetic(expression, expected):
    assert calculate(expression) == expected


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os').system('id')",
        "2**10000000",
        "[1]*100000000",
        "1/0",
        'float("nan")',
        "9" * 400,
        "2**2**20",
    ],
)
def test_calculator_rejects_unsafe_or_unbounded_input(expression):
    with pytest.raises(ValueError):
        calculate(expression)


def test_citation_validation_rejects_unknown_and_fabricated_evidence():
    sources = {"chunk-a": "The retention period is 30 days."}
    citations = [
        {"chunk_id": "chunk-a", "quote": "retention period is 30 days"},
        {"chunk_id": "chunk-b", "quote": "anything"},
        {"chunk_id": "chunk-a", "quote": "retention period is 90 days"},
    ]
    result = validate_citations(citations, sources)
    assert [r["valid"] for r in result] == [True, False, False]
    assert [r["reason"] for r in result] == [None, "unknown_source", "quote_not_found"]

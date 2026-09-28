"""Explicit metric definitions, missing-data semantics and regression directionality."""

import math
import re
import unicodedata
from statistics import mean


def normalize_answer(text: str) -> str:
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", text).casefold()))


def exact_match(answer: str, reference: str | None) -> float | None:
    return (
        None
        if reference is None
        else float(normalize_answer(answer) == normalize_answer(reference))
    )


def retrieval_metrics(
    retrieved: list[str], expected: list[str], *, k: int
) -> dict[str, float | None]:
    """Rank unique documents; precision denominator is k, including unfilled slots."""
    if not 1 <= k <= 100:
        raise ValueError("k must be between 1 and 100")
    names = ["precision_at_k", "recall_at_k", "hit_rate", "mrr"]
    relevant = set(expected)
    if not relevant:
        return dict.fromkeys(names)
    ranked = list(dict.fromkeys(retrieved))[:k]
    hits = [i + 1 for i, source in enumerate(ranked) if source in relevant]
    return dict(
        zip(
            names,
            [
                len(hits) / k,
                len(hits) / len(relevant),
                float(bool(hits)),
                1 / hits[0] if hits else 0.0,
            ],
            strict=True,
        )
    )


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * q
    low, high = math.floor(index), math.ceil(index)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def aggregate_operations(rows: list[dict]) -> dict:
    latencies = [row["latency_ms"] for row in rows if row.get("latency_ms") is not None]
    costs = [row["cost_usd"] for row in rows if row.get("cost_usd") is not None]
    return {
        "p50_latency_ms": percentile(latencies, 0.5),
        "p95_latency_ms": percentile(latencies, 0.95),
        "error_rate": mean(bool(row.get("error")) for row in rows) if rows else None,
        "input_tokens": sum(row.get("input_tokens", 0) for row in rows),
        "output_tokens": sum(row.get("output_tokens", 0) for row in rows),
        "total_cost_usd": sum(costs),
        "mean_cost_usd": mean(costs) if costs else None,
        "cost_coverage": len(costs) / len(rows) if rows else None,
        "queries": len(rows),
    }


LOWER_IS_BETTER = {
    "p50_latency_ms",
    "p95_latency_ms",
    "mean_cost_usd",
    "error_rate",
    "unsupported_claim_rate",
}
HIGHER_IS_BETTER = {
    "precision_at_k",
    "recall_at_k",
    "hit_rate",
    "mrr",
    "exact_match",
    "semantic_similarity",
    "citation_coverage",
    "citation_correctness",
    "groundedness",
    "answer_relevance",
    "tool_accuracy",
    "abstention_accuracy",
    "quote_correctness",
}


def compare_metrics(
    baseline: dict,
    candidate: dict,
    *,
    quality_tolerance: float = 0.05,
    operational_tolerance: float = 0.2,
) -> list[dict]:
    if any(not math.isfinite(v) or v < 0 for v in [quality_tolerance, operational_tolerance]):
        raise ValueError("Regression tolerances cannot be negative")
    results = []
    for metric in sorted(
        (baseline.keys() | candidate.keys()) & (LOWER_IS_BETTER | HIGHER_IS_BETTER)
    ):
        before, after = baseline.get(metric), candidate.get(metric)
        delta = None if before is None or after is None else after - before
        if delta is None:
            regression = None
        elif metric in HIGHER_IS_BETTER:
            regression = delta < -quality_tolerance
        elif metric in {"error_rate", "unsupported_claim_rate"}:
            regression = delta > quality_tolerance
        else:
            regression = delta > abs(before) * operational_tolerance
        results.append(
            {
                "metric": metric,
                "baseline": before,
                "candidate": after,
                "delta": delta,
                "regression": regression,
            }
        )
    return results

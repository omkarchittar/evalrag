import pytest

from evalrag.pricing import usage_record


def test_versioned_cost_accounts_for_cached_input_at_its_own_rate():
    usage = usage_record("generation", "gpt-4.1-mini-2025-04-14", 1_000_000, 100_000, 250_000)
    assert usage["cost_usd"] == pytest.approx(0.30 + 0.025 + 0.16)
    assert usage["pricing"]["version"] == "openai-standard-2026-09-28"


def test_unknown_models_and_nonstandard_endpoints_are_not_falsely_priced():
    assert usage_record("generation", "unknown", 100, 50)["cost_usd"] is None
    assert (
        usage_record("generation", "gpt-4.1-mini", 100, 50, standard_openai=False)["cost_usd"]
        is None
    )
    assert usage_record("embedding", "text-embedding-3-large", 1_000_000)[
        "cost_usd"
    ] == pytest.approx(0.13)


@pytest.mark.parametrize("values", [(-1, 0, 0), (10, 0, 11), (True, 0, 0), (10, float("nan"), 0)])
def test_invalid_usage_cannot_make_plausible_cost(values):
    with pytest.raises(ValueError):
        usage_record("generation", "gpt-4.1-mini", *values)

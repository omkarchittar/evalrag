"""Versioned standard API estimates; missing prices are unknown, never zero.

Source model pages verified 2026-09-28; see docs/pricing.md. These are estimates,
not invoices, and exclude tax, negotiated discounts and non-standard service tiers.
"""

import re

VERSION = "openai-standard-2026-09-28"
RATES = {
    "gpt-4.1-mini": {"input": 0.40, "cached_input": 0.10, "output": 1.60},
    "text-embedding-3-small": {"input": 0.02, "cached_input": 0.02, "output": 0.0},
    "text-embedding-3-large": {"input": 0.13, "cached_input": 0.13, "output": 0.0},
}


def usage_record(
    kind: str,
    model: str,
    input_tokens: int,
    output_tokens: int = 0,
    cached_tokens: int = 0,
    *,
    standard_openai: bool = True,
) -> dict:
    if (
        any(type(v) is not int or v < 0 for v in [input_tokens, output_tokens, cached_tokens])
        or cached_tokens > input_tokens
    ):
        raise ValueError("Invalid usage counters")
    key = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", model)
    rates = RATES.get(key) if standard_openai else None
    cost = (
        None
        if rates is None
        else (
            (input_tokens - cached_tokens) * rates["input"]
            + cached_tokens * rates["cached_input"]
            + output_tokens * rates["output"]
        )
        / 1_000_000
    )
    return {
        "kind": kind,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
        "cost_usd": cost,
        "pricing": {"version": VERSION, "per_million_usd": rates} if rates else None,
    }

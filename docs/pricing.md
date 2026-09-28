# Cost estimates and source provenance

Catalog version: `openai-standard-2026-09-28`. Values were checked against OpenAI's
model pages on 2026-09-28. Rates below are USD per one million tokens for standard
API use; they are estimates, not billing records.

| Model | Input | Cached input | Output | Source |
|---|---:|---:|---:|---|
| GPT-4.1 mini | 0.40 | 0.10 | 1.60 | [OpenAI model page](https://developers.openai.com/api/docs/models/gpt-4.1-mini) |
| text-embedding-3-small | 0.02 | 0.02 | — | [OpenAI model page](https://developers.openai.com/api/docs/models/text-embedding-3-small) |
| text-embedding-3-large | 0.13 | 0.13 | — | [OpenAI model page](https://developers.openai.com/api/docs/models/text-embedding-3-large) |

Generation estimates subtract reported cached input tokens from regular input tokens
before applying the separate rates. Dated model snapshots inherit their base model's
catalog entry. Each observed provider call persists its actual model identity, usage,
selected rates and catalog version so later changes cannot rewrite old estimates.

Unknown model prices or custom provider endpoints yield `null` cost. If a provider
failure makes total usage unknown, prior reported tokens remain available but the
query's total cost is `null` and `usage_complete` is false. A refused, truncated or
schema-invalid completion with valid reported usage still records those tokens.
Failed HTTP calls without a usage payload are not assumed free. Failures before any
provider call (for example, a missing key) incur zero observed provider cost.

The estimate excludes negotiated discounts, taxes, batch discounts, non-standard
service tiers and provider-side charges not represented by the token counters.
Review the provider's current pricing before using estimates for spending decisions.

The generation adapter follows the documented [function calling contract](https://developers.openai.com/api/docs/guides/function-calling)
and [Chat Completions API](https://platform.openai.com/docs/api-reference/chat/create).
Both tool arguments and final answers use strict schemas. Application validation
still runs on every result; schema adherence does not establish factual correctness.

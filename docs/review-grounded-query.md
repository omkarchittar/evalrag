# Grounded query review — 2026-09-28

Reviewed independently against the committed API/worker base `10f0637`.

| Finding | Fix and regression evidence |
|---|---|
| Null/list nested provider objects escaped as AttributeError | Boundary validates object shapes; malformed responses become sanitized persisted provider failures |
| RemoteProtocolError bypassed network failure handling | Generation and embedding adapters catch TransportError; disconnect tests assert safe retryable errors |
| Repeated tool searches duplicated source content beyond budget | Subsequent hits return existing-context references; captured prompts contain each source once across four completions |
| Partial query configuration ignored deployment default model | Resolve omitted model from settings before validating the complete configuration; HTTP regression covers alternate default |
| Valid usage disappeared on refusal/truncation/schema failures | ProviderError carries validated usage; query trace records known billing counters even when no answer can be returned |

Additional coverage includes foreign-workspace sources/metadata, membership revocation
during generation, citation fabrication, tool argument attacks, duplicate call IDs,
maximum tool steps, context selection, cached-token prices and unknown price semantics.

Re-review: **approved, no blocking issues remain**. The reviewer independently ran
40 targeted PostgreSQL tests. Full suite: **159 passing tests**, no skipped database
tests. Native API/worker smoke uses a controlled local provider; no live-model accuracy
or production-load claim is implied. Semantic evaluation and the full release remain
unfinished work.

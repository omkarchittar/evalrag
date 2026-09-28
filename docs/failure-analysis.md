# Failure analysis and measurement limits

These are verified software failure modes, not observations from a live-model benchmark.
The [test suite](../backend/tests) uses controlled provider responses to make each failure
repeatable. The separate [benchmark procedure](../benchmarks/README.md) measures actual model
behavior; its live reports have not been produced yet.

| Failure or ambiguity | Product response | Direct evidence |
| --- | --- | --- |
| An answer cites a foreign chunk, unseen context or fabricated quote | Withhold unsupported claims; retain validation findings in the trace | `test_rag.py`: unsupported claims and context-budget tests |
| A provider fails after retrieval has consumed tokens | Persist the failure and observed usage; total cost remains unknown when coverage is incomplete | `test_rag.py`: generation-failure and refusal-usage tests |
| A tool requests a foreign document, invalid arithmetic or repeated call ID | Scoped allowlist rejects unsafe calls; repeated IDs cannot reexecute | `test_rag.py`: metadata, invalid-tool and duplicate-ID tests |
| A document changes after an experiment snapshot | Fail before provider calls; never combine changed evidence with earlier results | `test_evaluation_worker.py`: corpus-change and changed-provider tests |
| A worker restarts during evaluation | Resume only unfinished cases using the saved snapshot | `test_evaluation_worker.py`: recovery test |
| A candidate loses scores or cost coverage | Return an inconclusive comparison rather than a misleading pass | `test_evaluation.py`: operational-coverage and protocol-change tests |
| A PDF has no extractable text or attempts decompression amplification | Return a bounded, explicit ingestion failure | `test_ingestion.py`: no-text, repeated-stream, page/text limit tests |

Quote matching proves that cited bytes are present; it cannot prove that a claim logically
follows from them. The semantic judge estimates groundedness and citation support, and can
itself be wrong. Embedding similarity rewards related meaning, while exact match can reject
valid paraphrases. Those metrics should be read together with the answer and source evidence.

The 60-case authored corpus is small and related in vocabulary. It does not measure unseen
domains, multilingual queries, scanned documents, concurrent load or adversaries outside its
labels. Cost estimates depend on reported tokens and a dated price catalog; they are not a bill.

## Required live report

Run both documented configurations on the same checksummed corpus and dataset. Retain complete
run JSON, config/protocol hashes, returned model identities, per-case traces and the comparison
report. Publish retrieval precision/recall/hit rate, semantic coverage/support, unsupported claims,
error/abstention rates, p50/p95 latency and estimated cost with coverage. Explain each failed or
unexpected case by ID and inspect its retrieved evidence, generated claims, citations and tools.
Separate retrieval misses, generation errors, judge disagreement and transport failures. Keep
failures in denominators and report an inconclusive gate when required observations are missing.

No claim about live benchmark quality should be made until those records exist.

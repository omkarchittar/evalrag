# Meridian policy benchmark

60 authored questions over eight original, explicitly fictional Meridian Labs policy documents.
No company data, provider outputs, measured performance or live-model results are included in this
bundle. `manifest.json` records the SHA-256 checksum of every document; `dataset.json` carries the
reference answers, expected source checksums, abstention labels, expected tools and tags.

| Case group | Count | Purpose |
| --- | ---: | --- |
| Policy questions | 48 | Retrieval, cited answers, metadata and resistance to a quoted instruction |
| Arithmetic questions | 6 | Calculator use with document-backed operands |
| Unanswerable/adversarial questions | 6 | Explicit abstention without inventing missing facts |

Two of the policy cases request metadata lookup. Calculator and metadata expectations are explicit
labels, so benchmark runs enable agent mode. The documents' security-training quotation is untrusted
source content, not an instruction to the application or evaluator.

## Run the benchmark

Start the API and a separate worker with the same database, provider URL and provider credentials.
Bootstrap an account as described in the repository README. Run these commands from the repository
root using the installed backend virtual environment. Each command prompts for the account password;
CI can supply `EVALRAG_BENCHMARK_PASSWORD` through a secret environment variable. Tokens and passwords
are never written to the state file or reports.

```sh
# Creates a dedicated workspace, dataset and small/large embedding knowledge bases.
# Uploading queues real provider embedding calls; running evaluations incurs generation/judge usage.
backend/.venv/bin/python -m evalrag.benchmark --email admin@example.com seed
```

State defaults to `.data/meridian.json`, which is git-ignored. Repeating `seed` with the same state
reuses recorded resources and checksum-idempotent uploads. The state is bound to the API and corpus.
An interrupted request whose response was lost can leave an unused workspace/dataset; the command
never deletes remote resources. Use a new state path for a new benchmark environment.

Wait for all eight documents in **both** knowledge bases to reach `ready` (inspect the API or UI).
A failed ingestion needs correction before a benchmark run; the runner refuses partial or extra
corpora. It also checks that the API dataset still matches the authored bundle.

```sh
backend/.venv/bin/python -m evalrag.benchmark --email admin@example.com run \
  --index small --name 'Small / top 5' --key meridian-small-top5-v1 --top-k 5 --wait 1800

backend/.venv/bin/python -m evalrag.benchmark --email admin@example.com run \
  --index large --name 'Large / top 3' --key meridian-large-top3-v1 --top-k 3 --wait 1800
```

Record the run IDs printed before waiting. Reuse a key only to retry the **same** request; changed
parameters with the same key receive HTTP 409. `--wait 0` (the default) returns immediately. A timed-out
wait does not cancel the durable run. Worker restarts resume missing cases, preserving prior results.
Use `--prompt concise-v1` to compare prompt variants. `--model` and `--evaluator` must be enabled in the
deployment; omitted values use its default model. `--no-semantics` disables judge/similarity calls and
leaves those metrics null. Runs with different evaluation protocols cannot be compared.

```sh
backend/.venv/bin/python -m evalrag.benchmark --email admin@example.com report BASELINE_RUN_ID \
  --output .data/baseline.json --traces
backend/.venv/bin/python -m evalrag.benchmark --email admin@example.com report CANDIDATE_RUN_ID \
  --output .data/candidate.json --traces
backend/.venv/bin/python -m evalrag.benchmark --email admin@example.com compare \
  BASELINE_RUN_ID CANDIDATE_RUN_ID --output .data/comparison.json
```

`compare` exits **0** for a passing gate, **1** for a regression or inconclusive comparison, and **2**
for a command/API failure. Defaults allow quality drops of 0.05 absolute and latency/cost increases
of 20% relative; pass `--quality-tolerance` and `--operational-tolerance` to make the criteria explicit.
Reports export persisted observations, configuration, provenance and optional full traces. A report
from a queued/running run is a partial report, clearly marked by its stored status and result count.
Inspect traces before publishing: they contain source text and answers. The tool cannot independently
verify that a configured endpoint really is the named provider; an endpoint fingerprint is provenance,
not attestation.

## Measurement contract

- Expected sources are document byte checksums, so equivalent corpora indexed with different models
  can share labels. Retrieval metrics use the initial top-k search, deduplicate document hits, and do
  not let later agent searches inflate retriever recall. Precision divides relevant document hits by
  configured k, including empty slots. Recall divides by expected documents; MRR uses the first hit.
- Exact match normalizes Unicode, case, whitespace and punctuation. Full-sentence references can be
  answered with valid paraphrases, so exact match is deliberately strict and should be read alongside
  semantic similarity and inspected examples.
- Similarity is cosine similarity from actual `text-embedding-3-small` evaluator vectors (1536
  dimensions), independent of the index model under test. It is an estimate, not a proof of correctness.
- Quote correctness checks source membership/verbatim evidence deterministically. Groundedness,
  semantic citation correctness, unsupported-claim rate and answer relevance come from a separate
  structured judge; they remain model estimates with recorded prompt/schema fingerprints and usage.
- Expected abstention and tool use have explicit labels. No reference or no generated answer leaves
  inapplicable semantic metrics null. Failed queries remain in operational error rates and applicable
  labeled scores. Quality summaries include coverage so missing scores cannot masquerade as accuracy.
- Query latency and cost cover retrieval/generation/tool execution. Evaluator usage/cost is reported
  separately. Cost estimates use the dated catalog and actual reported tokens; custom endpoints and
  unknown model prices yield unknown costs. A comparison with incomplete cost coverage is inconclusive.
- Run inputs and results are immutable. Dataset changes after scheduling do not alter a snapshot.
  New documents are excluded from an existing run; changing its indexed evidence fails the run. Changed
  provider endpoint, prompt or judge protocol fails execution/resumption rather than mixing protocols.

The bundle is a compact engineering benchmark, not a representative production distribution. Its
small corpus, authored answers and related policy wording favor some retrieval strategies. A release
report should show both configurations, error/abstention/coverage rates, failing examples, exact model
identities, dated cost assumptions and run hashes. Human review and a separate unseen corpus are still
needed before generalizing measured scores. Automated contract tests and local controlled-provider
smoke tests establish software behavior; they are never presented as live-model benchmark results.

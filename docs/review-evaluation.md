# Evaluation increment review

Reviewed locally against `41721d2`, 2026-09-28. Independent reviewer approved the final increment.

| Finding | Resolution and evidence |
| --- | --- |
| Missing query-cost coverage could pass a regression gate | Incomplete cost coverage or lost operational scores now makes comparison inconclusive; regression tests cover missing and reduced cost coverage. Native custom-provider comparison also refuses a passing gate. |
| Locked dataset could retain stale SQLAlchemy version | Refresh under the row lock before snapshotting; PostgreSQL identity-map regression verifies the current version is recorded. |
| Endpoint changes could mix evaluation protocols | Freeze an opaque endpoint fingerprint in each run; worker execution/resumption and comparisons check it. Raw URLs/credentials are not stored in run configuration. |
| Benchmark runner sent an invalid agent configuration field | Use `agent_mode`; test validates the generated payload against the real API schema. |
| Runner could execute an edited dataset as the authored benchmark | Compare canonical API case content to the bundle before submission. |

No material findings were deferred. The reviewer independently ran five targeted tests; the full
185-test PostgreSQL suite and native two-run CLI smoke were run by the implementation agent.
Controlled provider responses are transport/evaluation contract fixtures, not live model benchmarks.

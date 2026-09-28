"use client";
import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useWorkspace } from "@/components/workspace";
import {
  Heading,
  Panel,
  ErrorNotice,
  Loading,
  Empty,
  Status,
  Pagination,
  Metric,
  Json,
  metricName,
  number,
  percent,
  money,
} from "@/components/ui";
import { TraceView } from "@/components/trace-view";
import { useResource } from "@/lib/use-resource";
import type { Run, Page, Case, Trace, Scores } from "@/lib/types";
interface Result {
  id: string;
  case: Case;
  trace_id: string;
  metrics: Record<string, unknown>;
  answer: string | null;
  abstained: boolean;
  error_code: string | null;
  latency_ms: number;
}
export default function RunPage() {
  const { run } = useParams<{ run: string }>();
  return <RunDetail key={run} id={run} />;
}
function RunDetail({ id }: { id: string }) {
  const { workspace, base } = useWorkspace();
  const run = useResource<Run>(`/evaluation-runs/${id}`, 2500);
  const [offset, setOffset] = useState(0);
  const results = useResource<Page<Result>>(
    `/evaluation-runs/${id}/results?limit=20&offset=${offset}`,
    2500,
  );
  const [selected, setSelected] = useState<Result>();
  const r = run.data;
  if (r && r.workspace_id !== workspace.id)
    return <ErrorNotice message="Run does not belong to this workspace." />;
  return (
    <>
      <ErrorNotice message={run.error || results.error} />
      {r ? (
        <>
          <Heading
            eyebrow="IMMUTABLE EXPERIMENT"
            title={r.name}
            description={`${r.completed_cases} of ${r.total_cases} cases recorded`}
          >
            <Status value={r.status} />
            <Link
              className="button secondary"
              href={`${base}/compare?candidate=${r.id}`}
            >
              Compare this run
            </Link>
          </Heading>
          <div
            className="progress"
            role="progressbar"
            aria-label="Evaluation progress"
            aria-valuenow={r.completed_cases}
            aria-valuemin={0}
            aria-valuemax={r.total_cases || 1}
          >
            <span
              style={{
                width: `${r.total_cases ? (r.completed_cases / r.total_cases) * 100 : 0}%`,
              }}
            />
          </div>
          {r.error_code && (
            <ErrorNotice message={`Evaluation failed: ${r.error_code}`} />
          )}
          <div className="metrics">
            <Metric
              label="Groundedness"
              value={percent(r.metrics?.quality?.groundedness)}
              detail={`Coverage ${percent(r.metrics?.coverage?.groundedness)}`}
            />
            <Metric
              label="Recall at K"
              value={percent(r.metrics?.quality?.recall_at_k)}
              detail={`Coverage ${percent(r.metrics?.coverage?.recall_at_k)}`}
            />
            <Metric
              label="P95 query latency"
              value={
                r.metrics?.operations?.p95_latency_ms == null
                  ? "Not measured"
                  : `${number(r.metrics?.operations.p95_latency_ms)} ms`
              }
            />
            <Metric
              label="Mean query cost"
              value={money(r.metrics?.operations?.mean_cost_usd)}
              detail={`Known coverage ${percent(r.metrics?.operations?.cost_coverage)}`}
            />
          </div>
          <Panel
            title="Quality & coverage"
            subtitle="Missing labels or failed measurements stay unmeasured. Model-estimated scores are observations, not guarantees."
          >
            <ScoreTable
              scores={r.metrics?.quality}
              coverage={r.metrics?.coverage}
            />
          </Panel>
          <Panel
            title="Case results"
            subtitle="Inspect failures, references and the complete query trace."
          >
            {results.data?.items.length ? (
              <>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Question</th>
                        <th>Outcome</th>
                        <th>Evaluation</th>
                        <th>Latency</th>
                      </tr>
                    </thead>
                    <tbody>
                      {results.data.items.map((item) => (
                        <tr key={item.id}>
                          <td>
                            <button
                              className="text-button"
                              onClick={() => setSelected(item)}
                            >
                              {item.case.question}
                            </button>
                          </td>
                          <td>
                            <Status
                              value={
                                item.error_code
                                  ? "error"
                                  : item.abstained
                                    ? "abstained"
                                    : "answered"
                              }
                            />
                          </td>
                          <td>
                            {typeof item.metrics.evaluation_error === "string"
                              ? item.metrics.evaluation_error
                              : "Recorded"}
                          </td>
                          <td>{number(item.latency_ms)} ms</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  offset={offset}
                  total={results.data.total}
                  onChange={setOffset}
                />
              </>
            ) : (
              <Empty
                title={
                  r.status === "completed"
                    ? "No case results"
                    : "Waiting for case results"
                }
              >
                The separate worker records each case as it finishes.
              </Empty>
            )}
          </Panel>
          {selected && (
            <CaseDetail
              key={selected.id}
              result={selected}
              close={() => setSelected(undefined)}
            />
          )}
          <Panel
            title="Reproducibility record"
            subtitle="The run uses these saved inputs even if the source dataset changes."
          >
            <div className="trace-details">
              <dl className="hashes">
                <dt>Dataset hash</dt>
                <dd>{r.dataset_hash}</dd>
                <dt>Corpus hash</dt>
                <dd>{r.corpus_hash}</dd>
              </dl>
              <details>
                <summary>Frozen configuration</summary>
                <Json value={r.config} />
              </details>
              <details>
                <summary>Operational and evaluator measurements</summary>
                <Json
                  value={{
                    operations: r.metrics?.operations,
                    evaluator: r.metrics?.evaluator,
                    evaluation_error_rate: r.metrics?.evaluation_error_rate,
                    failed_cases: r.metrics?.failed_cases,
                  }}
                />
              </details>
            </div>
          </Panel>
        </>
      ) : (
        !run.error && <Loading />
      )}
    </>
  );
}
function ScoreTable({
  scores,
  coverage,
}: {
  scores?: Scores;
  coverage?: Scores;
}) {
  return scores ? (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Metric</th>
            <th>Score</th>
            <th>Case coverage</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(scores).map(([key, value]) => (
            <tr key={key}>
              <td>{metricName(key)}</td>
              <td>{number(value, 4)}</td>
              <td>{percent(coverage?.[key])}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  ) : (
    <Empty title="Metrics appear when the run completes" />
  );
}
function CaseDetail({ result, close }: { result: Result; close: () => void }) {
  const trace = useResource<Trace>(`/query-traces/${result.trace_id}`);
  return (
    <>
      <Panel
        title="Case inspection"
        subtitle={result.case.question}
        action={
          <button className="button secondary small" onClick={close}>
            Close case
          </button>
        }
      >
        <div className="source-body">
          <h3>Reference answer</h3>
          <p>
            {result.case.expected_answer ??
              (result.case.expected_abstention
                ? "Expected abstention"
                : "Not labeled")}
          </p>
          <p>{result.case.notes}</p>
          <details>
            <summary>Case labels & measured scores</summary>
            <Json value={{ case: result.case, metrics: result.metrics }} />
          </details>
        </div>
      </Panel>
      <ErrorNotice message={trace.error} />
      {trace.data ? (
        <TraceView key={trace.data.id} trace={trace.data} />
      ) : (
        !trace.error && <Loading />
      )}
    </>
  );
}

"use client";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useWorkspace } from "@/components/workspace";
import {
  Heading,
  Panel,
  ErrorNotice,
  Loading,
  Empty,
  Pagination,
  Status,
  Json,
  metricName,
  number,
} from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import type { Run, Page } from "@/lib/types";
interface Comparison {
  passed: boolean;
  regression: boolean;
  inconclusive: boolean;
  missing_or_reduced_coverage: string[];
  metrics: {
    metric: string;
    baseline: number | null;
    candidate: number | null;
    delta: number | null;
    regression: boolean | null;
  }[];
  coverage: unknown;
  thresholds: unknown;
}
export default function Compare() {
  return (
    <Suspense fallback={<Loading />}>
      <CompareForm />
    </Suspense>
  );
}
function CompareForm() {
  const { workspace } = useWorkspace();
  const params = useSearchParams();
  const [baseline, setBaseline] = useState("");
  const [candidate, setCandidate] = useState(params.get("candidate") ?? "");
  const [comparison, setComparison] = useState<Comparison>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  return (
    <>
      <Heading
        eyebrow="REGRESSION CHECK"
        title="Compare runs"
        description="Hold the dataset, corpus and evaluation protocol constant. Measure the effect of a configuration change."
      />
      <Panel
        title="Select experiments"
        subtitle="Both runs must be completed and belong to this workspace."
      >
        <form
          className="form-body"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError(undefined);
            setComparison(undefined);
            const f = new FormData(e.currentTarget);
            try {
              setComparison(
                await api<Comparison>(
                  `/evaluation-runs/${encodeURIComponent(candidate)}/compare/${encodeURIComponent(baseline)}?quality_tolerance=${Number(f.get("quality"))}&operational_tolerance=${Number(f.get("operational"))}`,
                ),
              );
            } catch (e) {
              setError(errorMessage(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          <fieldset disabled={busy}>
            <div className="form-grid">
              <RunPicker
                label="Baseline"
                workspace={workspace.id}
                value={baseline}
                onChange={(v) => {
                  setBaseline(v);
                  setComparison(undefined);
                }}
              />
              <RunPicker
                label="Candidate"
                workspace={workspace.id}
                value={candidate}
                onChange={(v) => {
                  setCandidate(v);
                  setComparison(undefined);
                }}
              />
              <label>
                Quality tolerance (absolute)
                <input
                  name="quality"
                  type="number"
                  min={0}
                  max={1}
                  step={0.01}
                  defaultValue={0.05}
                  required
                  onChange={() => setComparison(undefined)}
                />
              </label>
              <label>
                Latency / cost tolerance (relative)
                <input
                  name="operational"
                  type="number"
                  min={0}
                  max={10}
                  step={0.05}
                  defaultValue={0.2}
                  required
                  onChange={() => setComparison(undefined)}
                />
              </label>
            </div>
          </fieldset>
          <p className="small muted">
            0.05 permits a 5-point quality decrease; 0.20 permits a 20% latency
            or cost increase. Missing cost coverage or reduced quality coverage
            makes the gate inconclusive.
          </p>
          <ErrorNotice message={error} />
          <button
            className="button"
            disabled={busy || !baseline || !candidate || baseline === candidate}
          >
            {busy ? "Comparing…" : "Compare experiments"}
          </button>
        </form>
      </Panel>
      {comparison && (
        <Panel
          title={
            comparison.passed
              ? "Regression check passed"
              : comparison.regression
                ? "Regression detected"
                : "Comparison inconclusive"
          }
          subtitle={
            comparison.inconclusive
              ? "Coverage or evaluator errors prevent a passing result."
              : "Measurements evaluated against the selected tolerances."
          }
          action={
            <Status
              value={
                comparison.passed
                  ? "completed"
                  : comparison.regression
                    ? "regression"
                    : "inconclusive"
              }
            />
          }
        >
          <div className="source-body">
            {comparison.missing_or_reduced_coverage.length > 0 && (
              <div className="notice">
                Missing or reduced coverage:{" "}
                {comparison.missing_or_reduced_coverage
                  .map(metricName)
                  .join(", ")}
              </div>
            )}
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Baseline</th>
                  <th>Candidate</th>
                  <th>Delta</th>
                  <th>Gate</th>
                </tr>
              </thead>
              <tbody>
                {comparison.metrics.map((m) => (
                  <tr key={m.metric}>
                    <td>{metricName(m.metric)}</td>
                    <td>{number(m.baseline, 5)}</td>
                    <td>{number(m.candidate, 5)}</td>
                    <td>
                      {m.delta == null
                        ? "Not measured"
                        : `${m.delta > 0 ? "+" : ""}${number(m.delta, 5)}`}
                    </td>
                    <td>
                      {m.regression === null ? (
                        "Not measured"
                      ) : m.regression ? (
                        <Status value="regression" />
                      ) : (
                        "Within tolerance"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="trace-details">
            <details>
              <summary>Coverage & thresholds</summary>
              <Json
                value={{
                  coverage: comparison.coverage,
                  thresholds: comparison.thresholds,
                }}
              />
            </details>
          </div>
        </Panel>
      )}
    </>
  );
}
function RunPicker({
  label,
  workspace,
  value,
  onChange,
}: {
  label: string;
  workspace: string;
  value: string;
  onChange: (s: string) => void;
}) {
  const [offset, setOffset] = useState(0);
  const resource = useResource<Page<Run>>(
    `/workspaces/${workspace}/evaluation-runs?limit=20&offset=${offset}`,
  );
  return (
    <div className="run-picker">
      <label>
        {label} run ID
        <input
          required
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Select below or paste a run ID"
        />
      </label>
      <ErrorNotice message={resource.error} />
      {resource.data ? (
        <>
          <div className="picker-list">
            {resource.data.items
              .filter((r) => r.status === "completed")
              .map((r) => (
                <button
                  type="button"
                  key={r.id}
                  className={value === r.id ? "selected" : ""}
                  onClick={() => onChange(r.id)}
                >
                  {r.name}
                  <small>{r.completed_cases} cases</small>
                </button>
              ))}
            {!resource.data.items.some((r) => r.status === "completed") && (
              <Empty title="No completed runs on this page" />
            )}
          </div>
          <Pagination
            offset={offset}
            total={resource.data.total}
            onChange={setOffset}
          />
        </>
      ) : (
        !resource.error && <Loading />
      )}
    </div>
  );
}

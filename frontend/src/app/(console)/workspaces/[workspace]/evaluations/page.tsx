"use client";
import { useRef, useState } from "react";
import Link from "next/link";
import { useWorkspace } from "@/components/workspace";
import { useAuth } from "@/components/auth";
import { useRouter } from "next/navigation";
import {
  Heading,
  Panel,
  ErrorNotice,
  Empty,
  Loading,
  Status,
  Pagination,
  date,
} from "@/components/ui";
import { QuerySettings, defaultQuery } from "@/components/query-settings";
import { api, errorMessage } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import type {
  Dataset,
  KnowledgeBase,
  Run,
  Page,
  QueryOptions,
  QueryConfig,
} from "@/lib/types";
export default function Evaluations() {
  const { workspace, base, canEdit } = useWorkspace();
  const { session } = useAuth();
  const router = useRouter();
  const [offset, setOffset] = useState(0);
  const [dataOffset, setDataOffset] = useState(0);
  const runs = useResource<Page<Run>>(
    `/workspaces/${workspace.id}/evaluation-runs?limit=20&offset=${offset}`,
    3000,
  );
  const datasets = useResource<Page<Dataset>>(
    `/workspaces/${workspace.id}/datasets?limit=20&offset=${dataOffset}`,
  );
  const [create, setCreate] = useState(false);
  const [start, setStart] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  return (
    <>
      <Heading
        eyebrow="MEASURE WHAT CHANGES"
        title="Evaluations"
        description="Author reference cases, freeze an experiment and inspect every result."
      >
        {canEdit && (
          <>
            <button
              className="button secondary"
              onClick={() => setCreate(!create)}
            >
              New dataset
            </button>
            <button className="button" onClick={() => setStart(!start)}>
              New evaluation
            </button>
          </>
        )}
      </Heading>
      <ErrorNotice message={error || runs.error || datasets.error} />
      {create && (
        <Panel title="Create a dataset">
          <form
            className="form-body"
            onSubmit={async (e) => {
              e.preventDefault();
              const name = String(new FormData(e.currentTarget).get("name"));
              setBusy(true);
              setError(undefined);
              try {
                const d = await api<Dataset>(
                  `/workspaces/${workspace.id}/datasets`,
                  { method: "POST", body: JSON.stringify({ name }) },
                  session!.csrf_token,
                );
                router.push(`${base}/datasets/${d.id}`);
              } catch (e) {
                setError(errorMessage(e));
              } finally {
                setBusy(false);
              }
            }}
          >
            <label>
              Dataset name
              <input name="name" required maxLength={200} />
            </label>
            <button className="button" disabled={busy}>
              Create dataset
            </button>
          </form>
        </Panel>
      )}
      {start && <RunLoader />}
      <Panel
        title="Evaluation runs"
        subtitle="Each run preserves its dataset, corpus and evaluation protocol."
      >
        {runs.data?.items.length ? (
          <>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Experiment</th>
                    <th>Status</th>
                    <th>Progress</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.data.items.map((r) => (
                    <tr key={r.id}>
                      <td>
                        <Link
                          className="text-link"
                          href={`${base}/evaluations/${r.id}`}
                        >
                          {r.name}
                        </Link>
                      </td>
                      <td>
                        <Status value={r.status} />
                      </td>
                      <td>
                        {r.completed_cases} / {r.total_cases} cases
                      </td>
                      <td>{date(r.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              offset={offset}
              total={runs.data.total}
              onChange={setOffset}
            />
          </>
        ) : runs.data ? (
          <Empty title="No evaluation runs yet">
            Create a reference dataset and start an experiment.
          </Empty>
        ) : (
          !runs.error && <Loading />
        )}
      </Panel>
      <Panel
        title="Reference datasets"
        subtitle="Versioned cases with expected answers, sources and tool behavior."
      >
        {datasets.data?.items.length ? (
          <>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Dataset</th>
                    <th>Cases</th>
                    <th>Version</th>
                  </tr>
                </thead>
                <tbody>
                  {datasets.data.items.map((d) => (
                    <tr key={d.id}>
                      <td>
                        <Link
                          className="text-link"
                          href={`${base}/datasets/${d.id}`}
                        >
                          {d.name}
                        </Link>
                      </td>
                      <td>{d.case_count}</td>
                      <td>v{d.version}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination
              offset={dataOffset}
              total={datasets.data.total}
              onChange={setDataOffset}
            />
          </>
        ) : datasets.data ? (
          <Empty title="No datasets yet" />
        ) : (
          !datasets.error && <Loading />
        )}
      </Panel>
    </>
  );
}
function RunLoader() {
  const { workspace } = useWorkspace();
  const bases = useResource<KnowledgeBase[]>(
    `/workspaces/${workspace.id}/knowledge-bases`,
  );
  const options = useResource<QueryOptions>("/query-options");
  const [offset, setOffset] = useState(0);
  const datasets = useResource<Page<Dataset>>(
    `/workspaces/${workspace.id}/datasets?limit=100&offset=${offset}`,
  );
  return (
    <Panel
      title="Start an evaluation"
      subtitle="Cases and indexed documents are snapshotted when you submit."
    >
      <ErrorNotice message={bases.error || options.error || datasets.error} />
      {bases.data && options.data && datasets.data ? (
        <>
          {bases.data.length && datasets.data.items.length ? (
            <RunForm
              key={offset}
              bases={bases.data}
              datasets={datasets.data.items}
              options={options.data}
            />
          ) : (
            <Empty title="Add a knowledge base and dataset first" />
          )}
          <Pagination
            limit={100}
            offset={offset}
            total={datasets.data.total}
            onChange={setOffset}
          />
        </>
      ) : (
        <Loading />
      )}
    </Panel>
  );
}
function RunForm({
  bases,
  datasets,
  options,
}: {
  bases: KnowledgeBase[];
  datasets: Dataset[];
  options: QueryOptions;
}) {
  const { workspace, base } = useWorkspace();
  const { session } = useAuth();
  const router = useRouter();
  const [config, setConfig] = useState<QueryConfig>(() =>
    defaultQuery(options),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const submission = useRef<{ body: string; key: string } | null>(null);
  return (
    <form
      className="form-body"
      onSubmit={async (e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        const body = JSON.stringify({
          name: f.get("name"),
          dataset_id: f.get("dataset"),
          knowledge_base_id: f.get("kb"),
          query: config,
          evaluate_semantics: f.get("semantics") === "on",
          evaluator_model: f.get("evaluator"),
        });
        if (submission.current?.body !== body)
          submission.current = { body, key: crypto.randomUUID() };
        setBusy(true);
        setError(undefined);
        try {
          const r = await api<Run>(
            `/workspaces/${workspace.id}/evaluation-runs`,
            {
              method: "POST",
              body,
              headers: { "Idempotency-Key": submission.current!.key },
            },
            session!.csrf_token,
          );
          router.push(`${base}/evaluations/${r.id}`);
        } catch (e) {
          setError(errorMessage(e));
        } finally {
          setBusy(false);
        }
      }}
    >
      <fieldset disabled={busy}>
        <div className="form-grid">
          <label>
            Run name
            <input name="name" required maxLength={200} />
          </label>
          <label>
            Dataset
            <select name="dataset">
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} · {d.case_count} cases · v{d.version}
                </option>
              ))}
            </select>
          </label>
          <label>
            Knowledge base
            <select name="kb">
              {bases.map((k) => (
                <option key={k.id} value={k.id}>
                  {k.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Evaluator model
            <select name="evaluator">
              {options.models.map((m) => (
                <option key={m}>{m}</option>
              ))}
            </select>
          </label>
        </div>
        <label className="checkbox">
          <input type="checkbox" name="semantics" defaultChecked />
          Evaluate semantic support and relevance
          <span>
            Uses additional model and embedding calls. Deterministic retrieval
            and quote checks always run.
          </span>
        </label>
        <QuerySettings value={config} onChange={setConfig} options={options} />
      </fieldset>
      <ErrorNotice message={error} />
      <button className="button" disabled={busy}>
        {busy ? "Submitting…" : "Start evaluation"}
      </button>
    </form>
  );
}

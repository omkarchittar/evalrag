"use client";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ArrowUp, SlidersHorizontal, MessageSquareText } from "lucide-react";
import { useAuth } from "@/components/auth";
import { useWorkspace } from "@/components/workspace";
import {
  Heading,
  Panel,
  ErrorNotice,
  Empty,
  Loading,
  Status,
  Pagination,
} from "@/components/ui";
import { QuerySettings, defaultQuery } from "@/components/query-settings";
import { TraceView } from "@/components/trace-view";
import { api, errorMessage } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import type {
  KnowledgeBase,
  QueryConfig,
  QueryOptions,
  Trace,
  Page,
} from "@/lib/types";
export default function Playground() {
  return (
    <Suspense fallback={<Loading />}>
      <Loader />
    </Suspense>
  );
}
function Loader() {
  const { workspace } = useWorkspace();
  const params = useSearchParams();
  const bases = useResource<KnowledgeBase[]>(
    `/workspaces/${workspace.id}/knowledge-bases`,
  );
  const options = useResource<QueryOptions>("/query-options");
  return (
    <>
      <Heading
        eyebrow="RETRIEVE · REASON · VERIFY"
        title="Playground"
        description="Ask your documents. Inspect the answer, its evidence and the work behind it."
      />
      <ErrorNotice message={bases.error || options.error} />
      {bases.data && options.data ? (
        bases.data.length ? (
          <PlaygroundForm
            bases={bases.data}
            options={options.data}
            initial={params.get("kb")}
          />
        ) : (
          <Empty title="Add a knowledge base first">
            Upload and index documents before asking a question.
          </Empty>
        )
      ) : (
        !bases.error && !options.error && <Loading />
      )}
    </>
  );
}
function PlaygroundForm({
  bases,
  options,
  initial,
}: {
  bases: KnowledgeBase[];
  options: QueryOptions;
  initial: string | null;
}) {
  const [kb, setKb] = useState(
    bases.find((k) => k.id === initial)?.id ?? bases[0].id,
  );
  return (
    <>
      <label className="kb-selector">
        Knowledge base
        <select value={kb} onChange={(e) => setKb(e.target.value)}>
          {bases.map((k) => (
            <option key={k.id} value={k.id}>
              {k.name}
            </option>
          ))}
        </select>
      </label>
      <QueryForm key={kb} kb={kb} options={options} />
    </>
  );
}
function QueryForm({ kb, options }: { kb: string; options: QueryOptions }) {
  const { session } = useAuth();
  const [config, setConfig] = useState<QueryConfig>(() =>
    defaultQuery(options),
  );
  const [trace, setTrace] = useState<Trace>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  const [offset, setOffset] = useState(0);
  const history = useResource<Page<Trace>>(
    `/knowledge-bases/${kb}/queries?limit=20&offset=${offset}`,
  );
  return (
    <div className="playground-grid">
      <div>
        <Panel title="Ask a question">
          <form
            className="form-body"
            onSubmit={async (e) => {
              e.preventDefault();
              const question = String(
                new FormData(e.currentTarget).get("question"),
              );
              setBusy(true);
              setError(undefined);
              setTrace(undefined);
              try {
                setTrace(
                  await api<Trace>(
                    `/knowledge-bases/${kb}/queries`,
                    {
                      method: "POST",
                      body: JSON.stringify({ question, config }),
                    },
                    session!.csrf_token,
                  ),
                );
                history.refresh();
              } catch (e) {
                setError(errorMessage(e));
              } finally {
                setBusy(false);
              }
            }}
          >
            <label>
              Question
              <textarea
                name="question"
                rows={3}
                maxLength={4000}
                required
                placeholder="What does our policy say about…?"
              />
            </label>
            <details>
              <summary>
                <SlidersHorizontal size={16} />
                Query settings
              </summary>
              <QuerySettings
                value={config}
                onChange={setConfig}
                options={options}
                disabled={busy}
              />
            </details>
            <div className="form-actions">
              <span className="muted small">
                {config.model} · top {config.top_k} ·{" "}
                {config.agent_mode ? "Agent" : "RAG"}
              </span>
              <button className="button" disabled={busy}>
                {busy ? "Retrieving & answering…" : "Ask question"}
                <ArrowUp size={17} />
              </button>
            </div>
            <ErrorNotice message={error} />
          </form>
        </Panel>
        {busy ? (
          <Loading />
        ) : trace ? (
          <TraceView key={trace.id} trace={trace} />
        ) : (
          <div className="playground-empty">
            <MessageSquareText size={32} />
            <h2>Start with a question.</h2>
            <p>Your answer, citations and execution trace will appear here.</p>
          </div>
        )}
      </div>
      <Panel title="Query history" subtitle="Saved queries for this collection">
        <ErrorNotice message={history.error} />
        {history.data?.items.length ? (
          <>
            <div className="history-list">
              {history.data.items.map((t) => (
                <button
                  key={t.id}
                  disabled={busy}
                  onClick={() => setTrace(t)}
                  className={trace?.id === t.id ? "selected" : ""}
                >
                  <strong>{t.question}</strong>
                  <Status value={t.outcome} />
                </button>
              ))}
            </div>
            <Pagination
              offset={offset}
              total={history.data.total}
              onChange={setOffset}
            />
          </>
        ) : history.data ? (
          <Empty title="No saved queries yet" />
        ) : (
          !history.error && <Loading />
        )}
      </Panel>
    </div>
  );
}

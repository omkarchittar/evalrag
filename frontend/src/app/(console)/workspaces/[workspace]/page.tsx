"use client";
import Link from "next/link";
import {
  ArrowRight,
  Database,
  FlaskConical,
  MessageSquareText,
} from "lucide-react";
import { useWorkspace } from "@/components/workspace";
import {
  Heading,
  Panel,
  ErrorNotice,
  Empty,
  Loading,
  Status,
  Metric,
  More,
  number,
  percent,
  money,
  date,
} from "@/components/ui";
import { useResource } from "@/lib/use-resource";
import type { Overview, KnowledgeBase } from "@/lib/types";
export default function Dashboard() {
  const { workspace, base } = useWorkspace();
  const overview = useResource<Overview>(
    `/workspaces/${workspace.id}/overview`,
    6000,
  );
  const bases = useResource<KnowledgeBase[]>(
    `/workspaces/${workspace.id}/knowledge-bases`,
  );
  const data = overview.data;
  return (
    <>
      <Heading
        eyebrow="WORKSPACE OVERVIEW"
        title={workspace.name}
        description="Follow the evidence from source to answer to evaluation."
      >
        <Link className="button" href={`${base}/playground`}>
          Open playground
          <ArrowRight size={17} />
        </Link>
      </Heading>
      <ErrorNotice message={overview.error || bases.error} />
      {data ? (
        <>
          <div className="metrics">
            <Metric
              label="Knowledge bases"
              value={data.knowledge_base_count}
              detail={`${Object.values(data.documents).reduce((a, b) => a + b, 0)} documents · ${data.documents.ready ?? 0} indexed`}
            />
            <Metric
              label="Queries observed"
              value={number(data.operations.queries)}
              detail={`Most recent ${data.operations_sample_limit} queries`}
            />
            <Metric
              label="P95 response time"
              value={
                data.operations.p95_latency_ms == null
                  ? "Not measured"
                  : `${number(data.operations.p95_latency_ms)} ms`
              }
              detail={`Error rate ${percent(data.operations.error_rate)}`}
            />
            <Metric
              label="Mean query cost"
              value={money(data.operations.mean_cost_usd)}
              detail={`Known cost coverage ${percent(data.operations.cost_coverage)}`}
            />
          </div>
          <div className="two-columns">
            <Panel
              title="Knowledge bases"
              subtitle="Your indexed evidence collections"
              action={<More href={`${base}/knowledge`}>View all</More>}
            >
              {bases.data?.length ? (
                bases.data.slice(0, 5).map((k) => (
                  <Link
                    className="list-row"
                    key={k.id}
                    href={`${base}/knowledge/${k.id}`}
                  >
                    <span className="tile-icon">
                      <Database size={20} />
                    </span>
                    <div>
                      <strong>{k.name}</strong>
                      <small>
                        {k.embedding_model} · {k.embedding_dimension} dimensions
                      </small>
                    </div>
                    <ArrowRight size={17} />
                  </Link>
                ))
              ) : (
                <Empty title="No knowledge bases yet">
                  Add a collection and upload source documents.
                </Empty>
              )}
            </Panel>
            <Panel
              title="Recent evaluations"
              subtitle="Immutable experiments, recorded outcomes"
              action={<More href={`${base}/evaluations`}>View all</More>}
            >
              {data.recent_runs.length ? (
                data.recent_runs.map((r) => (
                  <Link
                    className="list-row"
                    key={r.id}
                    href={`${base}/evaluations/${r.id}`}
                  >
                    <span className="tile-icon">
                      <FlaskConical size={20} />
                    </span>
                    <div>
                      <strong>{r.name}</strong>
                      <small>{date(r.created_at)}</small>
                    </div>
                    <Status value={r.status} />
                  </Link>
                ))
              ) : (
                <Empty title="Your next experiment starts here">
                  Create a dataset, run an evaluation, then compare a change.
                </Empty>
              )}
            </Panel>
          </div>
          <Panel
            title="Document pipeline"
            subtitle="Current ingestion state across this workspace"
          >
            <div className="pipeline">
              {["queued", "processing", "ready", "failed"].map((s) => (
                <div key={s}>
                  <Status value={s} />
                  <strong>{data.documents[s] ?? 0}</strong>
                </div>
              ))}
            </div>
          </Panel>
          <div className="hint-banner">
            <MessageSquareText size={24} />
            <div>
              <strong>Grounding starts with inspectable sources.</strong>
              <p>
                The playground shows the retrieved context, exact citation
                quotes and actual query trace.
              </p>
            </div>
            <More href={`${base}/playground`}>Ask a question</More>
          </div>
        </>
      ) : (
        !overview.error && <Loading />
      )}
    </>
  );
}

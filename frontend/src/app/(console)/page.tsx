"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Plus, ArrowUpRight, Layers3 } from "lucide-react";
import { useAuth } from "@/components/auth";
import {
  Heading,
  Panel,
  ErrorNotice,
  Empty,
  Loading,
  Status,
  date,
} from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import type { Workspace } from "@/lib/types";
export default function Workspaces() {
  const { session } = useAuth();
  const router = useRouter();
  const resource = useResource<Workspace[]>("/workspaces");
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  return (
    <>
      <Heading
        eyebrow="RESEARCH CONSOLE"
        title="Your workspaces"
        description="Bring knowledge, experiments and evidence together."
      >
        <button className="button" onClick={() => setOpen(!open)}>
          <Plus size={17} />
          New workspace
        </button>
      </Heading>
      <ErrorNotice message={error || resource.error} />
      {open && (
        <Panel title="Create a workspace">
          <form
            className="form-body"
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError(undefined);
              const name = String(new FormData(e.currentTarget).get("name"));
              try {
                const data = await api<Workspace>(
                  "/workspaces",
                  { method: "POST", body: JSON.stringify({ name }) },
                  session!.csrf_token,
                );
                router.push(`/workspaces/${data.id}`);
              } catch (e) {
                setError(errorMessage(e));
              } finally {
                setBusy(false);
              }
            }}
          >
            <label>
              Workspace name
              <input
                name="name"
                required
                maxLength={200}
                placeholder="Customer support research"
              />
            </label>
            <button className="button" disabled={busy}>
              {busy ? "Creating…" : "Create workspace"}
            </button>
          </form>
        </Panel>
      )}
      <div className="card-grid">
        {resource.data?.map((w) => (
          <Link
            className="workspace-card"
            key={w.id}
            href={`/workspaces/${w.id}`}
          >
            <div className="card-top">
              <span className="tile-icon">
                <Layers3 />
              </span>
              <ArrowUpRight size={18} />
            </div>
            <h2>{w.name}</h2>
            <Status value={w.role} />
            <p className="muted small">Created {date(w.created_at)}</p>
          </Link>
        ))}
      </div>
      {resource.data?.length === 0 && (
        <Empty title="Start with a workspace">
          Create a home for your documents and evaluation datasets.
        </Empty>
      )}
      {!resource.data && !resource.error && <Loading />}
      <div className="hint-banner">
        <Layers3 size={22} />
        <div>
          <strong>Keep each research context together.</strong>
          <p>
            Workspace membership scopes knowledge bases, queries and evaluation
            results.
          </p>
        </div>
      </div>
    </>
  );
}

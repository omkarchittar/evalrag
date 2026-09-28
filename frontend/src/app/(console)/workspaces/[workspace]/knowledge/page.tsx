"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Plus, Database, ArrowUpRight } from "lucide-react";
import { useAuth } from "@/components/auth";
import { useWorkspace } from "@/components/workspace";
import { Heading, Panel, ErrorNotice, Empty, Loading } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import type { KnowledgeBase } from "@/lib/types";
export default function Knowledge() {
  const { workspace, base, canEdit } = useWorkspace();
  const { session } = useAuth();
  const router = useRouter();
  const resource = useResource<KnowledgeBase[]>(
    `/workspaces/${workspace.id}/knowledge-bases`,
  );
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  return (
    <>
      <Heading
        eyebrow="EVIDENCE COLLECTIONS"
        title="Knowledge bases"
        description="Choose an embedding space and give your answers a source of truth."
      >
        {canEdit && (
          <button className="button" onClick={() => setOpen(!open)}>
            <Plus size={17} />
            New knowledge base
          </button>
        )}
      </Heading>
      <ErrorNotice message={error || resource.error} />
      {open && (
        <Panel
          title="Create a knowledge base"
          subtitle="Embedding and chunking settings define this collection’s index."
        >
          <form
            className="form-body"
            onSubmit={async (e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              setBusy(true);
              setError(undefined);
              try {
                const k = await api<KnowledgeBase>(
                  `/workspaces/${workspace.id}/knowledge-bases`,
                  {
                    method: "POST",
                    body: JSON.stringify({
                      name: f.get("name"),
                      description: f.get("description"),
                      embedding_model: f.get("embedding_model"),
                      embedding_dimension: Number(f.get("embedding_dimension")),
                      chunk_strategy: f.get("chunk_strategy"),
                      chunk_size: Number(f.get("chunk_size")),
                      chunk_overlap: Number(f.get("overlap")),
                    }),
                  },
                  session!.csrf_token,
                );
                router.push(`${base}/knowledge/${k.id}`);
              } catch (e) {
                setError(errorMessage(e));
              } finally {
                setBusy(false);
              }
            }}
          >
            <div className="form-grid">
              <label>
                Knowledge base name
                <input name="name" required maxLength={200} />
              </label>
              <label>
                Description
                <input name="description" maxLength={2000} />
              </label>
              <label>
                Embedding model
                <select name="embedding_model">
                  <option>text-embedding-3-small</option>
                  <option>text-embedding-3-large</option>
                </select>
              </label>
              <label>
                Embedding dimensions
                <input
                  name="embedding_dimension"
                  type="number"
                  min={1}
                  max={3072}
                  defaultValue={1536}
                  required
                />
              </label>
              <label>
                Chunk strategy
                <select name="chunk_strategy">
                  <option value="recursive">Recursive</option>
                  <option value="fixed">Fixed</option>
                </select>
              </label>
              <label>
                Chunk size (tokens)
                <input
                  name="chunk_size"
                  type="number"
                  min={8}
                  max={8192}
                  defaultValue={400}
                  required
                />
              </label>
              <label>
                Overlap (tokens)
                <input
                  name="overlap"
                  type="number"
                  min={0}
                  max={8191}
                  defaultValue={60}
                  required
                />
              </label>
            </div>
            <p className="muted small">
              Small supports up to 1,536 dimensions; large supports up to 3,072.
              Overlap must be smaller than chunk size.
            </p>
            <button className="button" disabled={busy}>
              {busy ? "Creating…" : "Create knowledge base"}
            </button>
          </form>
        </Panel>
      )}
      <div className="card-grid">
        {resource.data?.map((k) => (
          <Link
            className="workspace-card"
            key={k.id}
            href={`${base}/knowledge/${k.id}`}
          >
            <div className="card-top">
              <span className="tile-icon">
                <Database />
              </span>
              <ArrowUpRight size={18} />
            </div>
            <h2>{k.name}</h2>
            <p>{k.description || "Document collection"}</p>
            <div className="card-meta">
              <span>{k.embedding_model}</span>
              <span>
                {k.chunk_strategy} · {k.chunk_size} tokens
              </span>
            </div>
          </Link>
        ))}
      </div>
      {resource.data?.length === 0 && (
        <Empty title="No knowledge bases yet">
          Create your first collection to start indexing documents.
        </Empty>
      )}
      {!resource.data && !resource.error && <Loading />}
    </>
  );
}

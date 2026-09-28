"use client";
import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Upload, FileText, Download, ArrowRight } from "lucide-react";
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
  number,
} from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import type { KnowledgeBase, Document, Page } from "@/lib/types";
export default function KnowledgeDetail() {
  const { kb } = useParams<{ kb: string }>();
  return <Detail key={kb} id={kb} />;
}
function Detail({ id }: { id: string }) {
  const { workspace, base, canEdit } = useWorkspace();
  const { session } = useAuth();
  const resource = useResource<KnowledgeBase>(`/knowledge-bases/${id}`);
  const [offset, setOffset] = useState(0);
  const docs = useResource<Page<Document>>(
    `/knowledge-bases/${id}/documents?limit=20&offset=${offset}`,
    2500,
  );
  const [selected, setSelected] = useState<Document>();
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState<string>();
  const kb = resource.data;
  if (kb && kb.workspace_id !== workspace.id)
    return (
      <ErrorNotice message="Knowledge base does not belong to this workspace." />
    );
  return (
    <>
      <ErrorNotice message={resource.error} />
      {kb ? (
        <>
          <Heading
            eyebrow="KNOWLEDGE BASE"
            title={kb.name}
            description={
              kb.description ||
              "Manage the source material behind your answers."
            }
          >
            <Link className="button" href={`${base}/playground?kb=${kb.id}`}>
              Ask this collection
              <ArrowRight size={17} />
            </Link>
          </Heading>
          <div className="config-strip">
            <span>
              <strong>{kb.embedding_model}</strong>
              {kb.embedding_dimension} dimensions
            </span>
            <span>
              <strong>{kb.chunk_strategy} chunks</strong>
              {kb.chunk_size} tokens · {kb.chunk_overlap} overlap
            </span>
            <span>
              <strong>Index version {kb.index_version}</strong>Dense cosine
              retrieval
            </span>
          </div>
          {canEdit && (
            <Panel
              title="Add evidence"
              subtitle="Upload a PDF, Markdown or plain text document. Matching files are deduplicated by checksum."
            >
              <form
                className="upload-form"
                onSubmit={async (e) => {
                  e.preventDefault();
                  const form = e.currentTarget;
                  const body = new FormData(form);
                  setBusy(true);
                  setError(undefined);
                  setSuccess(undefined);
                  try {
                    const d = await api<Document>(
                      `/knowledge-bases/${id}/documents`,
                      { method: "POST", body },
                      session!.csrf_token,
                    );
                    setSuccess(
                      `${d.filename} received. Ingestion status is shown below.`,
                    );
                    form.reset();
                    setOffset(0);
                    docs.refresh();
                  } catch (e) {
                    setError(errorMessage(e));
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                <label>
                  Choose document
                  <input
                    type="file"
                    name="file"
                    accept=".pdf,.txt,.md"
                    required
                  />
                </label>
                <button className="button" disabled={busy}>
                  <Upload size={17} />
                  {busy ? "Uploading…" : "Upload document"}
                </button>
              </form>
              <ErrorNotice message={error} />
              {success && (
                <div className="notice" role="status">
                  {success}
                </div>
              )}
            </Panel>
          )}
          <Panel
            title="Documents"
            subtitle="Status updates automatically while the worker indexes your files."
          >
            <ErrorNotice message={docs.error} />
            {docs.data?.items.length ? (
              <>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Document</th>
                        <th>Status</th>
                        <th>Chunks</th>
                        <th>Embedding tokens</th>
                        <th>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {docs.data.items.map((d) => (
                        <tr key={d.id}>
                          <td>
                            <strong className="file-name">
                              <FileText size={16} />
                              {d.filename}
                            </strong>
                            <small>
                              {number(d.size_bytes / 1000, 1)} KB
                              {d.error_code && ` · ${d.error_code}`}
                            </small>
                          </td>
                          <td>
                            <Status value={d.status} />
                          </td>
                          <td>{number(d.chunk_count)}</td>
                          <td>{number(d.embedding_tokens)}</td>
                          <td>
                            <div className="actions">
                              <button
                                className="button secondary small"
                                disabled={!d.chunk_count}
                                onClick={() => setSelected(d)}
                              >
                                Inspect chunks
                              </button>
                              <a
                                className="icon-button"
                                aria-label={`Download ${d.filename}`}
                                href={`/api/documents/${d.id}/download`}
                              >
                                <Download size={17} />
                              </a>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <Pagination
                  offset={offset}
                  total={docs.data.total}
                  onChange={setOffset}
                />
              </>
            ) : docs.data ? (
              <Empty title="No documents yet">
                Upload evidence to make this collection searchable.
              </Empty>
            ) : (
              !docs.error && <Loading />
            )}
          </Panel>
          {selected && (
            <Chunks
              key={selected.id}
              document={selected}
              onClose={() => setSelected(undefined)}
            />
          )}
        </>
      ) : (
        !resource.error && <Loading />
      )}
    </>
  );
}
function Chunks({
  document,
  onClose,
}: {
  document: Document;
  onClose: () => void;
}) {
  const [offset, setOffset] = useState(0);
  const resource = useResource<
    Page<{
      id: string;
      page: number;
      ordinal: number;
      content: string;
      token_count: number;
    }>
  >(`/documents/${document.id}/chunks?limit=20&offset=${offset}`);
  return (
    <Panel
      title={`Chunks · ${document.filename}`}
      subtitle={`SHA-256 ${document.checksum}`}
      action={
        <button className="button secondary small" onClick={onClose}>
          Close chunks
        </button>
      }
    >
      <ErrorNotice message={resource.error} />
      {resource.data ? (
        <>
          <div className="chunks">
            {resource.data.items.map((c) => (
              <article key={c.id}>
                <span className="eyebrow">
                  PAGE {c.page} · CHUNK {c.ordinal + 1} · {c.token_count} TOKENS
                </span>
                <p>{c.content}</p>
              </article>
            ))}
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
    </Panel>
  );
}

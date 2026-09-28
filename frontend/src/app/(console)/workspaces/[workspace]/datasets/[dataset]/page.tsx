"use client";
import { useState } from "react";
import { useParams } from "next/navigation";
import { useWorkspace } from "@/components/workspace";
import { useAuth } from "@/components/auth";
import { Heading, Panel, ErrorNotice, Loading, Empty } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import type { Dataset, Case } from "@/lib/types";
const blank = (): Case => ({
  question: "",
  expected_answer: null,
  expected_abstention: null,
  expected_sources: [],
  expected_tool: null,
  tags: [],
  notes: "",
});
export default function DatasetPage() {
  const { dataset } = useParams<{ dataset: string }>();
  const { workspace } = useWorkspace();
  const [reload, setReload] = useState(0);
  const resource = useResource<Dataset>(`/datasets/${dataset}`);
  return (
    <>
      <ErrorNotice message={resource.error} />
      {resource.data ? (
        resource.data.workspace_id === workspace.id ? (
          <Editor
            key={`${resource.data.id}-${resource.data.version}-${reload}`}
            dataset={resource.data}
            replace={(data) => {
              resource.replace(data);
              setReload((n) => n + 1);
            }}
          />
        ) : (
          <ErrorNotice message="Dataset does not belong to this workspace." />
        )
      ) : (
        !resource.error && <Loading />
      )}
    </>
  );
}
function Editor({
  dataset,
  replace,
}: {
  dataset: Dataset;
  replace: (data: Dataset) => void;
}) {
  const { canEdit } = useWorkspace();
  const { session } = useAuth();
  const [cases, setCases] = useState<(Case & { editorKey: string })[]>(() =>
    (dataset.cases ?? []).map((c) => ({
      ...c,
      editorKey: crypto.randomUUID(),
    })),
  );
  const [error, setError] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [success, setSuccess] = useState<string>();
  function update(index: number, change: Partial<Case>) {
    setCases(cases.map((c, i) => (i === index ? { ...c, ...change } : c)));
    setDirty(true);
    setSuccess(undefined);
  }
  return (
    <>
      <Heading
        eyebrow={`REFERENCE DATASET · VERSION ${dataset.version}`}
        title={dataset.name}
        description={`${cases.length} cases · Edits create a new version. Existing runs keep their original snapshot.`}
      >
        <a
          className="button secondary"
          href={`/api/datasets/${dataset.id}/export`}
          target="_blank"
          rel="noreferrer"
        >
          Export JSON
        </a>
        {canEdit && (
          <button
            className="button secondary"
            disabled={busy}
            onClick={async () => {
              if (
                !dirty ||
                window.confirm(
                  "Discard unsaved changes and reload the latest dataset?",
                )
              ) {
                setBusy(true);
                setError(undefined);
                try {
                  replace(await api<Dataset>(`/datasets/${dataset.id}`));
                } catch (e) {
                  setError(errorMessage(e));
                } finally {
                  setBusy(false);
                }
              }
            }}
          >
            Reload latest
          </button>
        )}
      </Heading>
      <ErrorNotice message={error} />
      {success && (
        <div className="notice" role="status">
          {success}
        </div>
      )}
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError(undefined);
          setSuccess(undefined);
          try {
            const saved = await api<Dataset>(
              `/datasets/${dataset.id}/cases`,
              {
                method: "PUT",
                body: JSON.stringify({
                  version: dataset.version,
                  cases: cases.map(({ id, editorKey, ...rest }) => {
                    void editorKey;
                    void id;
                    return rest;
                  }),
                }),
              },
              session!.csrf_token,
            );
            setDirty(false);
            replace(saved);
          } catch (e) {
            setError(errorMessage(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        <fieldset disabled={!canEdit || busy}>
          {cases.map((c, i) => (
            <Panel
              key={c.editorKey}
              title={`Case ${i + 1}`}
              subtitle={c.tags.length ? c.tags.join(" · ") : undefined}
              action={
                canEdit ? (
                  <button
                    className="button secondary small"
                    type="button"
                    onClick={() => {
                      setCases(cases.filter((_, n) => n !== i));
                      setDirty(true);
                    }}
                  >
                    Remove case {i + 1}
                  </button>
                ) : undefined
              }
            >
              <div className="form-body">
                <label>
                  Question {i + 1}
                  <textarea
                    aria-label={`Question ${i + 1}`}
                    value={c.question}
                    required
                    maxLength={4000}
                    rows={2}
                    onChange={(e) => update(i, { question: e.target.value })}
                  />
                </label>
                <div className="form-grid">
                  <label>
                    Expected outcome
                    <select
                      value={
                        c.expected_abstention === null
                          ? "unlabeled"
                          : c.expected_abstention
                            ? "abstain"
                            : "answer"
                      }
                      onChange={(e) =>
                        update(i, {
                          expected_abstention:
                            e.target.value === "unlabeled"
                              ? null
                              : e.target.value === "abstain",
                          ...(e.target.value === "abstain"
                            ? { expected_answer: null }
                            : {}),
                        })
                      }
                    >
                      <option value="unlabeled">Not labeled</option>
                      <option value="answer">Answer</option>
                      <option value="abstain">Abstain</option>
                    </select>
                  </label>
                  <label>
                    Expected tool
                    <select
                      value={c.expected_tool ?? ""}
                      onChange={(e) =>
                        update(i, { expected_tool: e.target.value || null })
                      }
                    >
                      <option value="">Not labeled</option>
                      <option>document_search</option>
                      <option>calculator</option>
                      <option>metadata_lookup</option>
                    </select>
                  </label>
                </div>
                {c.expected_abstention !== true && (
                  <label>
                    Reference answer
                    <textarea
                      aria-label="Reference answer"
                      value={c.expected_answer ?? ""}
                      maxLength={8000}
                      rows={2}
                      onChange={(e) =>
                        update(i, { expected_answer: e.target.value || null })
                      }
                    />
                  </label>
                )}
                <label>
                  Expected source checksums
                  <textarea
                    defaultValue={c.expected_sources.join("\n")}
                    placeholder="One SHA-256 document checksum per line"
                    rows={2}
                    onChange={(e) =>
                      update(i, {
                        expected_sources: e.target.value
                          .split(/\s+/)
                          .filter(Boolean),
                      })
                    }
                  />
                  <span className="field-help">
                    Find the 64-character checksum in the document’s chunk
                    inspector. Leave blank for unlabeled retrieval.
                  </span>
                </label>
                <label>
                  Tags
                  <input
                    defaultValue={c.tags.join(", ")}
                    maxLength={800}
                    placeholder="travel, policy"
                    onChange={(e) =>
                      update(i, {
                        tags: e.target.value
                          .split(",")
                          .map((s) => s.trim())
                          .filter(Boolean),
                      })
                    }
                  />
                </label>
                <label>
                  Notes
                  <textarea
                    aria-label="Notes"
                    value={c.notes}
                    maxLength={2000}
                    rows={2}
                    onChange={(e) => update(i, { notes: e.target.value })}
                  />
                </label>
              </div>
            </Panel>
          ))}
        </fieldset>
        {cases.length === 0 && (
          <Empty title="No reference cases yet">
            Add questions with expected answers, source checksums or abstention
            labels.
          </Empty>
        )}
        {canEdit && (
          <div className="sticky-actions">
            <span className="muted small">
              {dirty ? "Unsaved changes" : `Saved version ${dataset.version}`}
            </span>
            <button
              className="button secondary"
              type="button"
              disabled={busy || cases.length >= 200}
              onClick={() => {
                setCases([
                  ...cases,
                  { ...blank(), editorKey: crypto.randomUUID() },
                ]);
                setDirty(true);
              }}
            >
              Add case
            </button>
            <button className="button" disabled={busy || !dirty}>
              {busy ? "Saving…" : "Save dataset"}
            </button>
          </div>
        )}
      </form>
    </>
  );
}

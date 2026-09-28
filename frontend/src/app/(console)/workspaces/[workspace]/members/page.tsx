"use client";
import { useState } from "react";
import { useWorkspace } from "@/components/workspace";
import { useAuth } from "@/components/auth";
import { Heading, Panel, ErrorNotice, Loading, Status } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
export default function Members() {
  const { workspace, refresh: refreshWorkspace } = useWorkspace();
  const { session } = useAuth();
  const resource = useResource<
    { id: string; name: string; email: string; role: string }[]
  >(`/workspaces/${workspace.id}/members`);
  const [error, setError] = useState<string>();
  const [success, setSuccess] = useState(false);
  const [busy, setBusy] = useState(false);
  return (
    <>
      <Heading
        eyebrow="WORKSPACE ACCESS"
        title="Members"
        description="Owners manage membership. Editors maintain evidence and experiments. Viewers can inspect and query."
      />
      <ErrorNotice message={error || resource.error} />
      {success && (
        <div className="notice" role="status">
          Membership saved.
        </div>
      )}
      {workspace.role === "owner" && (
        <Panel
          title="Add or update a member"
          subtitle="The person must already have an active account. Enter their email to add access or change their role."
        >
          <form
            className="form-body"
            onSubmit={async (e) => {
              e.preventDefault();
              const form = e.currentTarget;
              setBusy(true);
              setError(undefined);
              setSuccess(false);
              try {
                await api(
                  `/workspaces/${workspace.id}/members`,
                  {
                    method: "PUT",
                    body: JSON.stringify(
                      Object.fromEntries(new FormData(form)),
                    ),
                  },
                  session!.csrf_token,
                );
                form.reset();
                setSuccess(true);
                resource.refresh();
                refreshWorkspace();
              } catch (e) {
                setError(errorMessage(e));
              } finally {
                setBusy(false);
              }
            }}
          >
            <div className="form-grid">
              <label>
                Member email
                <input type="email" name="email" required />
              </label>
              <label>
                Workspace role
                <select name="role" defaultValue="viewer">
                  <option>viewer</option>
                  <option>editor</option>
                  <option>owner</option>
                </select>
              </label>
            </div>
            <button className="button" disabled={busy}>
              {busy ? "Saving…" : "Save membership"}
            </button>
          </form>
        </Panel>
      )}
      <Panel title="Workspace members">
        {resource.data ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Person</th>
                  <th>Email</th>
                  <th>Role</th>
                </tr>
              </thead>
              <tbody>
                {resource.data.map((m) => (
                  <tr key={m.id}>
                    <td>
                      <strong>{m.name}</strong>
                    </td>
                    <td>{m.email}</td>
                    <td>
                      <Status value={m.role} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          !resource.error && <Loading />
        )}
      </Panel>
    </>
  );
}

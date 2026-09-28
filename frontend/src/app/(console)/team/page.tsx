"use client";
import { useState } from "react";
import { useAuth } from "@/components/auth";
import { Heading, Panel, ErrorNotice, Loading } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import type { User } from "@/lib/types";
export default function Team() {
  const { session } = useAuth();
  const admin = session!.user.role === "admin";
  const resource = useResource<User[]>(admin ? "/admin/users" : null);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string>();
  const [success, setSuccess] = useState<string>();
  const [busy, setBusy] = useState(false);
  if (!admin)
    return (
      <ErrorNotice message="Account administration requires an administrator." />
    );
  return (
    <>
      <Heading
        eyebrow="DEPLOYMENT ACCESS"
        title="Account administration"
        description="Provision accounts, then grant workspace membership separately."
      >
        <button className="button" onClick={() => setOpen(!open)}>
          New account
        </button>
      </Heading>
      <ErrorNotice message={error || resource.error} />
      {success && (
        <div className="notice" role="status">
          {success}
        </div>
      )}
      {open && (
        <Panel
          title="Create an account"
          subtitle="Share the initial password securely with its owner. No email is sent."
        >
          <form
            className="form-body"
            onSubmit={async (e) => {
              e.preventDefault();
              const form = e.currentTarget;
              setBusy(true);
              setError(undefined);
              setSuccess(undefined);
              try {
                await api(
                  "/admin/users",
                  {
                    method: "POST",
                    body: JSON.stringify(
                      Object.fromEntries(new FormData(form)),
                    ),
                  },
                  session!.csrf_token,
                );
                form.reset();
                setOpen(false);
                setSuccess("Account created.");
                resource.refresh();
              } catch (e) {
                setError(errorMessage(e));
              } finally {
                setBusy(false);
              }
            }}
          >
            <div className="form-grid">
              <label>
                Full name
                <input name="name" required maxLength={200} />
              </label>
              <label>
                Email address
                <input name="email" type="email" required />
              </label>
              <label>
                Initial password
                <input
                  type="password"
                  name="password"
                  required
                  minLength={12}
                  maxLength={1024}
                  autoComplete="new-password"
                />
              </label>
              <label>
                Role
                <select name="role">
                  <option>member</option>
                  <option>admin</option>
                </select>
              </label>
            </div>
            <button className="button" disabled={busy}>
              Create account
            </button>
          </form>
        </Panel>
      )}
      <Panel
        title="Accounts"
        subtitle="Role changes and deactivation revoke active sessions."
      >
        {resource.data ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Person</th>
                  <th>Role</th>
                  <th>Active</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {resource.data.map((u) => (
                  <Account
                    key={`${u.id}-${u.role}-${u.active}`}
                    user={u}
                    onSaved={() => {
                      setSuccess("Account updated.");
                      resource.refresh();
                    }}
                    onError={setError}
                  />
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
function Account({
  user,
  onSaved,
  onError,
}: {
  user: User;
  onSaved: () => void;
  onError: (s: string) => void;
}) {
  const { session } = useAuth();
  const [role, setRole] = useState(user.role);
  const [active, setActive] = useState(user.active);
  const [busy, setBusy] = useState(false);
  return (
    <tr>
      <td>
        <strong>{user.name}</strong>
        <small>{user.email}</small>
      </td>
      <td>
        <select
          aria-label={`Role for ${user.name}`}
          value={role}
          onChange={(e) => setRole(e.target.value as User["role"])}
        >
          <option>member</option>
          <option>admin</option>
        </select>
      </td>
      <td>
        <input
          type="checkbox"
          aria-label={`Active account for ${user.name}`}
          checked={active}
          onChange={(e) => setActive(e.target.checked)}
        />
      </td>
      <td>
        <button
          className="button secondary small"
          disabled={busy || (role === user.role && active === user.active)}
          onClick={async () => {
            setBusy(true);
            try {
              await api(
                `/admin/users/${user.id}`,
                { method: "PATCH", body: JSON.stringify({ role, active }) },
                session!.csrf_token,
              );
              if (user.id === session!.user.id)
                window.dispatchEvent(new Event("session-expired"));
              else onSaved();
            } catch (e) {
              onError(errorMessage(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          Save
        </button>
      </td>
    </tr>
  );
}

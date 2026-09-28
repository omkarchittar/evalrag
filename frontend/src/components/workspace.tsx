"use client";
import { createContext, useContext } from "react";
import { useParams } from "next/navigation";
import { useResource } from "@/lib/use-resource";
import type { Workspace } from "@/lib/types";
import { ErrorNotice, Loading } from "./ui";
const Context = createContext<{
  workspace: Workspace;
  refresh: () => void;
} | null>(null);
export function WorkspaceGate({ children }: { children: React.ReactNode }) {
  const { workspace } = useParams<{ workspace: string }>();
  const resource = useResource<Workspace[]>("/workspaces");
  const current = resource.data?.find((w) => w.id === workspace);
  if (resource.error) return <ErrorNotice message={resource.error} />;
  if (!resource.data) return <Loading />;
  if (!current)
    return (
      <ErrorNotice message="Workspace not found or access is no longer available." />
    );
  return (
    <Context.Provider value={{ workspace: current, refresh: resource.refresh }}>
      <div key={current.id}>{children}</div>
    </Context.Provider>
  );
}
export function useWorkspace() {
  const context = useContext(Context);
  if (!context) throw new Error("Workspace context required");
  return {
    ...context,
    base: `/workspaces/${context.workspace.id}`,
    canEdit: context.workspace.role !== "viewer",
  };
}

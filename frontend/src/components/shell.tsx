"use client";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import { useState } from "react";
import {
  Layers3,
  LayoutDashboard,
  Database,
  MessageSquareText,
  FlaskConical,
  GitCompareArrows,
  Users,
  LogOut,
  Menu,
  X,
  ArrowLeft,
} from "lucide-react";
import { useAuth, AuthGate } from "./auth";
import { ErrorNotice } from "./ui";
import { errorMessage } from "@/lib/api";
export function Brand() {
  return (
    <Link href="/" className="brand">
      <span>
        <Layers3 size={23} />
      </span>
      EvalRAG<i>LAB</i>
    </Link>
  );
}
export function Shell({ children }: { children: React.ReactNode }) {
  const { session, logout } = useAuth();
  const pathname = usePathname();
  const params = useParams();
  const workspace =
    typeof params.workspace === "string" ? params.workspace : null;
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string>();
  const base = workspace ? `/workspaces/${workspace}` : "";
  const links = workspace
    ? ([
        [base, "Overview", LayoutDashboard],
        [`${base}/knowledge`, "Knowledge bases", Database],
        [`${base}/playground`, "Playground", MessageSquareText],
        [`${base}/evaluations`, "Evaluations", FlaskConical],
        [`${base}/compare`, "Compare runs", GitCompareArrows],
        [`${base}/members`, "Members", Users],
      ] as const)
    : [];
  return (
    <AuthGate>
      <a href="#main" className="skip">
        Skip to content
      </a>
      <header className="mobile-bar">
        <Brand />
        <button
          className="icon-button"
          aria-label={open ? "Close navigation" : "Open navigation"}
          aria-expanded={open}
          onClick={() => setOpen(!open)}
        >
          {open ? <X /> : <Menu />}
        </button>
      </header>
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <Brand />
        <nav aria-label="Main navigation">
          <span className="nav-label">RESEARCH CONSOLE</span>
          <Link
            href="/"
            onClick={() => setOpen(false)}
            className={pathname === "/" ? "active" : ""}
          >
            <ArrowLeft size={17} />
            All workspaces
          </Link>
          {links.map(([href, label, Icon]) => (
            <Link
              key={href}
              href={href}
              onClick={() => setOpen(false)}
              className={
                pathname === href ||
                (href !== base && pathname.startsWith(href + "/"))
                  ? "active"
                  : ""
              }
              aria-current={pathname === href ? "page" : undefined}
            >
              <Icon size={18} />
              {label}
            </Link>
          ))}
          {session?.user.role === "admin" && (
            <Link
              href="/team"
              onClick={() => setOpen(false)}
              className={pathname === "/team" ? "active" : ""}
            >
              <Users size={18} />
              Account administration
            </Link>
          )}
        </nav>
        <div className="sidebar-note">
          <span className="signal" />
          Evidence before confidence.
          <p>
            Inspect the sources.
            <br />
            Measure the change.
          </p>
        </div>
        <div className="profile">
          <span className="avatar">
            {session?.user.name.slice(0, 2).toUpperCase()}
          </span>
          <div>
            <strong>{session?.user.name}</strong>
            <small>{session?.user.role}</small>
          </div>
          <button
            className="icon-button"
            aria-label="Sign out"
            onClick={async () => {
              try {
                await logout();
              } catch (e) {
                setError(errorMessage(e));
              }
            }}
          >
            <LogOut size={18} />
          </button>
        </div>
        <ErrorNotice message={error} />
      </aside>
      <main id="main" className="main" tabIndex={-1}>
        <div className="topline">
          <span>EvalRAG / {workspace ? "Workspace" : "Console"}</span>
          <span className="muted">Retrieval · Grounding · Evaluation</span>
        </div>
        {children}
        <footer className="footer">
          EvalRAG{" "}
          <span>Answers with evidence. Experiments you can reproduce.</span>
        </footer>
      </main>
    </AuthGate>
  );
}

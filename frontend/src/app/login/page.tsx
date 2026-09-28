"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  SearchCheck,
  ChartNoAxesCombined,
  Quote,
} from "lucide-react";
import { Brand } from "@/components/shell";
import { useAuth } from "@/components/auth";
import { ErrorNotice } from "@/components/ui";
import { errorMessage } from "@/lib/api";
export default function Login() {
  const { session, loading, login } = useAuth();
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string>();
  useEffect(() => {
    if (session && !loading) router.replace("/");
  }, [session, loading, router]);
  return (
    <main className="login-page">
      <section className="login-story">
        <Brand />
        <div>
          <span className="eyebrow">THE RETRIEVAL RESEARCH WORKSPACE</span>
          <h1>
            Every answer.
            <br />
            <em>Backed by evidence.</em>
          </h1>
          <p>
            Build your knowledge base, inspect how answers are grounded, and
            measure what changes between experiments.
          </p>
          <div className="principles">
            {[
              [
                SearchCheck,
                "Retrieve with purpose",
                "Trace each answer to its source.",
              ],
              [
                Quote,
                "Inspect the evidence",
                "Read the exact quotes behind a claim.",
              ],
              [
                ChartNoAxesCombined,
                "Measure every change",
                "Compare quality, latency and cost.",
              ],
            ].map(([Icon, title, text]) => {
              const I = Icon as typeof SearchCheck;
              return (
                <div key={String(title)}>
                  <I size={22} />
                  <div>
                    <strong>{String(title)}</strong>
                    <span>{String(text)}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
        <small>A workspace for reliable AI systems.</small>
      </section>
      <section className="login-form">
        <span className="eyebrow">WELCOME BACK</span>
        <h2>Open your research workspace.</h2>
        <p className="muted">Sign in to continue your experiments.</p>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            const data = new FormData(e.currentTarget);
            setBusy(true);
            setError(undefined);
            try {
              await login(
                String(data.get("email")),
                String(data.get("password")),
              );
              router.replace("/");
            } catch (e) {
              setError(errorMessage(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            Email address
            <input
              name="email"
              type="email"
              required
              autoComplete="username"
              placeholder="you@company.com"
            />
          </label>
          <label>
            Password
            <input
              name="password"
              type="password"
              required
              maxLength={1024}
              autoComplete="current-password"
            />
          </label>
          <ErrorNotice message={error} />
          <button className="button" disabled={busy || loading}>
            {busy ? "Signing in…" : "Sign in"}
            <ArrowRight size={18} />
          </button>
        </form>
        <p className="small muted">
          Need access? Ask your administrator to create an account.
        </p>
      </section>
    </main>
  );
}

import Link from "next/link";
import { ArrowUpRight, AlertCircle, LoaderCircle } from "lucide-react";
export function ErrorNotice({ message }: { message?: string | null }) {
  return message ? (
    <div className="notice error" role="alert">
      <AlertCircle size={18} />
      <span>{message}</span>
    </div>
  ) : null;
}
export function Loading() {
  return (
    <div className="empty" role="status">
      <LoaderCircle className="spin" size={22} />
      Loading workspace data…
    </div>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      {children && <p>{children}</p>}
    </div>
  );
}
export function Heading({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  children?: React.ReactNode;
}) {
  return (
    <header className="page-heading">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      <div className="actions">{children}</div>
    </header>
  );
}
export function Panel({
  title,
  subtitle,
  children,
  action,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
export function Status({ value }: { value: string }) {
  return (
    <span
      className={`status ${["ready", "completed", "answered", "owner", "success"].includes(value) ? "good" : ["failed", "error", "regression"].includes(value) ? "bad" : "neutral"}`}
    >
      <i />
      {value.replaceAll("_", " ")}
    </span>
  );
}
export function Pagination({
  offset,
  total,
  onChange,
  limit = 20,
}: {
  offset: number;
  total: number;
  onChange: (n: number) => void;
  limit?: number;
}) {
  return (
    <div className="pagination">
      <span>
        {total
          ? `${offset + 1}–${Math.min(offset + limit, total)} of ${total}`
          : "0 results"}
      </span>
      <div className="actions">
        <button
          type="button"
          className="button secondary small"
          disabled={offset === 0}
          onClick={() => onChange(Math.max(0, offset - limit))}
        >
          Previous
        </button>
        <button
          type="button"
          className="button secondary small"
          disabled={offset + limit >= total}
          onClick={() => onChange(offset + limit)}
        >
          Next
        </button>
      </div>
    </div>
  );
}
export function More({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <Link className="text-link" href={href}>
      {children}
      <ArrowUpRight size={16} />
    </Link>
  );
}
export function Metric({
  label,
  value,
  detail,
}: {
  label: string;
  value: React.ReactNode;
  detail?: string;
}) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      {detail && <small>{detail}</small>}
    </div>
  );
}
export function Json({ value }: { value: unknown }) {
  return <pre className="json">{JSON.stringify(value, null, 2)}</pre>;
}
export function number(value: number | null | undefined, digits = 0) {
  return value == null
    ? "Not measured"
    : value.toLocaleString(undefined, { maximumFractionDigits: digits });
}
export function percent(value: number | null | undefined) {
  return value == null ? "Not measured" : `${(value * 100).toFixed(1)}%`;
}
export function money(value: number | null | undefined) {
  return value == null ? "Unknown" : `$${value.toFixed(6)}`;
}
export function date(value: string) {
  return new Date(value).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}
export function metricName(key: string) {
  return key
    .replaceAll("_", " ")
    .replace(/\b(p50|p95|mrr)\b/g, (x) => x.toUpperCase());
}

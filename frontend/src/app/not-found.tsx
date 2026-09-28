import Link from "next/link";
export default function NotFound() {
  return (
    <main className="full-state">
      <h1>Page not found</h1>
      <p>This address does not match a console page.</p>
      <Link className="button" href="/">
        Go to workspaces
      </Link>
    </main>
  );
}

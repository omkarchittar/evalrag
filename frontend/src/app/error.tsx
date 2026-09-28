"use client";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <main className="full-state">
      <h1>Something interrupted this view.</h1>
      <p>Please try loading it again.</p>
      <button className="button" onClick={reset}>
        Try again
      </button>
    </main>
  );
}

"use client";

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center px-6">
      <p className="text-sm font-semibold uppercase tracking-widest text-[var(--brand)]">Application error</p>
      <h1 className="mt-3 text-4xl font-semibold">The workspace could not be loaded.</h1>
      <p className="mt-4 leading-7 text-[var(--muted)]">
        Your scientific data has not been changed. Retry the request or inspect the service health logs.
      </p>
      <button
        className="mt-8 w-fit rounded-full bg-[var(--brand-deep)] px-5 py-3 font-semibold text-white"
        onClick={reset}
        type="button"
      >
        Try again
      </button>
    </main>
  );
}


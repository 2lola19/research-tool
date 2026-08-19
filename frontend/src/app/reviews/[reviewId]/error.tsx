"use client";

export default function ReviewError({ reset }: { reset: () => void }) {
  return (
    <main className="mx-auto min-h-screen w-full max-w-7xl px-6 py-8 sm:px-10 lg:px-14">
      <section className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-900" role="alert">
        <h1 className="text-2xl font-semibold">The review workspace encountered an error</h1>
        <p className="mt-2 text-sm">No scientific decision was assumed or changed. Retry the server-authorized read.</p>
        <button className="mt-5 rounded-full bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white" onClick={() => reset()} type="button">Retry</button>
      </section>
    </main>
  );
}

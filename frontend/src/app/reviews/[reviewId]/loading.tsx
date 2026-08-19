export default function ReviewLoading() {
  return (
    <main aria-busy="true" aria-live="polite" className="mx-auto min-h-screen w-full max-w-7xl px-6 py-8 sm:px-10 lg:px-14">
      <div className="animate-pulse space-y-6">
        <div className="h-4 w-56 rounded bg-slate-200" />
        <div className="h-10 w-2/3 rounded bg-slate-200" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4"><div className="h-28 rounded-2xl bg-slate-200" /><div className="h-28 rounded-2xl bg-slate-200" /><div className="h-28 rounded-2xl bg-slate-200" /><div className="h-28 rounded-2xl bg-slate-200" /></div>
        <div className="h-72 rounded-2xl bg-slate-200" />
      </div>
      <p className="mt-6 text-sm text-[var(--muted)]">Loading server-authorized review operations…</p>
    </main>
  );
}

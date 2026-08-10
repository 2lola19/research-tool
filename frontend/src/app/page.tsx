import { getBackendHealth } from "@/lib/api";

const pillars = [
  ["Orchestrate", "Durable jobs, retries, checkpoints, and visible progress."],
  ["Specialize", "Focused research engines with explicit scientific responsibilities."],
  ["Structure", "Canonical evidence in typed records, never in chat history."],
  ["Trace", "Source, actor, model, prompt, version, and change provenance."],
  ["Govern", "Human review wherever errors could alter scientific conclusions."],
] as const;

const upcoming = [
  "Organizations and access boundaries",
  "Review projects and memberships",
  "Versioned protocols",
  "Persisted workflows and provenance",
] as const;

export default async function Home() {
  const backend = await getBackendHealth();
  const isReady = backend.status === "healthy";

  return (
    <main className="mx-auto min-h-screen w-full max-w-7xl px-6 py-8 sm:px-10 lg:px-14">
      <header className="flex items-center justify-between border-b border-[var(--line)] pb-6">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.22em] text-[var(--brand)]">
            Evidence workspace
          </p>
          <p className="mt-1 text-sm text-[var(--muted)]">Foundation milestone</p>
        </div>
        <div
          className="flex items-center gap-2 rounded-full border border-[var(--line)] bg-white px-4 py-2 text-sm shadow-sm"
          aria-label={`API ${backend.status}`}
        >
          <span
            className={`h-2.5 w-2.5 rounded-full ${isReady ? "bg-emerald-500" : "bg-amber-500"}`}
          />
          API {isReady ? "ready" : "unavailable"}
        </div>
      </header>

      <section className="grid gap-12 py-16 lg:grid-cols-[1.25fr_0.75fr] lg:items-end lg:py-24">
        <div>
          <p className="mb-5 text-sm font-semibold text-[var(--brand)]">Trustworthy synthesis, by design</p>
          <h1 className="max-w-4xl text-5xl font-semibold leading-[1.02] tracking-[-0.045em] sm:text-6xl lg:text-7xl">
            Evidence that can show its work.
          </h1>
          <p className="mt-7 max-w-2xl text-lg leading-8 text-[var(--muted)]">
            A systematic review platform built around structured evidence, deterministic science,
            explicit provenance, and accountable human decisions.
          </p>
        </div>

        <aside className="rounded-3xl border border-[var(--line)] bg-[var(--surface)] p-7 shadow-[0_24px_70px_rgb(20_35_28/8%)]">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--muted)]">Next foundation work</p>
          <ol className="mt-5 space-y-4">
            {upcoming.map((item, index) => (
              <li className="flex gap-4 text-sm" key={item}>
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[#edf4f0] font-semibold text-[var(--brand)]">
                  {index + 1}
                </span>
                <span className="pt-1 text-[var(--foreground)]">{item}</span>
              </li>
            ))}
          </ol>
        </aside>
      </section>

      <section className="border-t border-[var(--line)] py-10" aria-labelledby="architecture-heading">
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--brand)]">Architecture</p>
            <h2 id="architecture-heading" className="mt-2 text-3xl font-semibold tracking-[-0.025em]">
              Five permanent pillars
            </h2>
          </div>
          <p className="max-w-lg text-sm leading-6 text-[var(--muted)]">
            Features arrive incrementally. These boundaries remain stable as the product grows.
          </p>
        </div>

        <div className="mt-8 grid gap-px overflow-hidden rounded-2xl border border-[var(--line)] bg-[var(--line)] md:grid-cols-2 lg:grid-cols-5">
          {pillars.map(([title, description], index) => (
            <article className="min-h-52 bg-white p-6" key={title}>
              <span className="text-sm font-semibold text-[var(--accent)]">0{index + 1}</span>
              <h3 className="mt-8 text-xl font-semibold">{title}</h3>
              <p className="mt-3 text-sm leading-6 text-[var(--muted)]">{description}</p>
            </article>
          ))}
        </div>
      </section>

      <footer className="flex flex-col gap-2 border-t border-[var(--line)] py-8 text-sm text-[var(--muted)] sm:flex-row sm:items-center sm:justify-between">
        <span>Local-first. Provider-neutral. Reproducibility-led.</span>
        <span>Phase 0/1 · v0.1.0</span>
      </footer>
    </main>
  );
}


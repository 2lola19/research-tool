import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";

import { getAIProposal, getAIWorkspace } from "@/lib/ai-api";

import { createSearchSuggestion, decideProposal } from "./actions";

type Props = {
  params: Promise<{ reviewId: string }>;
  searchParams: Promise<{ proposal?: string; error?: string; updated?: string }>;
};

const field = "mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-sm";
const button = "rounded-full bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white";

export default async function AIWorkspacePage({ params, searchParams }: Props) {
  const [{ reviewId }, query, store] = await Promise.all([params, searchParams, cookies()]);
  const token = store.get("review_access_token")?.value;
  const organizationId = store.get("review_organization_id")?.value;
  if (!token || !organizationId) redirect("/login");
  const workspacePromise = getAIWorkspace(token, organizationId, reviewId);
  const proposalPromise = query.proposal
    ? getAIProposal(token, organizationId, reviewId, query.proposal)
    : Promise.resolve(null);
  const [workspace, proposal] = await Promise.all([workspacePromise, proposalPromise]);
  if (workspace.status === "unauthorized") redirect("/login?error=session_expired");

  return (
    <main className="mx-auto min-h-screen w-full max-w-7xl px-6 py-8 sm:px-10 lg:px-14">
      <header className="border-b border-[var(--line)] pb-7">
        <Link className="text-sm font-semibold text-[var(--brand)] hover:underline" href="/reviews">
          &larr; Review projects
        </Link>
        <p className="mt-6 text-xs font-bold uppercase tracking-[0.22em] text-[var(--brand)]">
          Provider-neutral, proposal-only execution
        </p>
        <h1 className="mt-2 text-3xl font-semibold">AI settings and runs</h1>
        <p className="mt-2 max-w-3xl text-sm text-[var(--muted)]">
          AI output is never canonical scientific state. Every result is validated and requires an
          explicit human decision. This phase uses only the deterministic offline mock provider.
        </p>
      </header>

      {query.error ? <p className="mt-6 rounded-xl bg-red-50 p-4 text-red-800">Request rejected safely.</p> : null}
      {query.updated ? <p className="mt-6 rounded-xl bg-emerald-50 p-4 text-emerald-900">Decision recorded.</p> : null}

      <section className="grid gap-6 py-9 lg:grid-cols-2">
        <div className="rounded-2xl border border-[var(--line)] bg-white p-6">
          <h2 className="text-xl font-semibold">Execution policy</h2>
          <dl className="mt-4 space-y-2 text-sm">
            <div><dt className="font-semibold">Provider</dt><dd>{workspace.registry.providers[0]?.key ?? "Unavailable"} — no network</dd></div>
            <div><dt className="font-semibold">Model</dt><dd>{workspace.registry.models[0]?.display_name ?? "Unavailable"}</dd></div>
            <div><dt className="font-semibold">Human review</dt><dd>Mandatory; auto-accept disabled</dd></div>
            <div><dt className="font-semibold">Usage</dt><dd>{String(workspace.usage.input_tokens ?? 0)} input / {String(workspace.usage.output_tokens ?? 0)} output tokens</dd></div>
          </dl>
        </div>
        <form action={createSearchSuggestion.bind(null, reviewId)} className="rounded-2xl border border-[var(--line)] bg-white p-6">
          <h2 className="text-xl font-semibold">Search-query suggestion</h2>
          <p className="mt-2 text-sm text-[var(--muted)]">Creates a reviewable draft only; it cannot replace a SearchStrategyVersion.</p>
          <label className="mt-4 block text-xs font-semibold">Objective<input className={field} name="objective" required /></label>
          <label className="mt-4 block text-xs font-semibold">Current query<textarea className={field} name="query" required rows={4} /></label>
          <button className={`${button} mt-5`} type="submit">Generate mock proposal</button>
        </form>
      </section>

      {proposal ? (
        <section className="rounded-2xl border border-[var(--line)] bg-white p-6">
          <h2 className="text-xl font-semibold">Proposal review</h2>
          <pre className="mt-4 overflow-auto rounded-xl bg-slate-950 p-4 text-xs text-slate-100">{JSON.stringify(proposal.structured_value, null, 2)}</pre>
          <p className="mt-3 text-sm">State: <strong>{String(proposal.state)}</strong></p>
          {proposal.state === "PENDING_REVIEW" ? (
            <div className="mt-4 flex flex-wrap gap-3">
              {(["ACCEPTED", "REJECTED"] as const).map((decision) => (
                <form action={decideProposal.bind(null, reviewId, String(proposal.id), decision)} key={decision}>
                  <input className={field} name="reason" placeholder="Reason (optional)" />
                  <button className={`${button} mt-2`} type="submit">{decision === "ACCEPTED" ? "Accept draft" : "Reject"}</button>
                </form>
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="border-t border-[var(--line)] py-9">
        <h2 className="text-2xl font-semibold">Recent immutable runs</h2>
        <div className="mt-5 space-y-3">
          {workspace.runs.map((run) => (
            <article className="rounded-xl border border-[var(--line)] bg-white p-4" key={run.id}>
              <p className="font-semibold">{run.task_type} · {run.state}</p>
              <p className="mt-1 text-xs text-[var(--muted)]">Input hash {run.input_hash}</p>
              {run.identical_prior_run_id ? <p className="mt-1 text-xs text-amber-800">Identical prior run: {run.identical_prior_run_id}</p> : null}
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

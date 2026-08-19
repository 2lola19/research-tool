import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";

import { getAIProposal, getAIWorkspace } from "@/lib/ai-api";
import { getAICopilotWorkspace } from "@/lib/ai-copilot-api";

import { createCopilotPolicy, createCopilotQuery, createSearchSuggestion, decideProposal } from "./actions";

type Props = {
  params: Promise<{ reviewId: string }>;
  searchParams: Promise<{
    proposal?: string;
    error?: string;
    updated?: string;
    copilot?: string;
    copilot_error?: string;
  }>;
};

const field = "mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-sm";
const button = "rounded-full bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white";

export default async function AIWorkspacePage({ params, searchParams }: Props) {
  const [{ reviewId }, query, store] = await Promise.all([params, searchParams, cookies()]);
  const token = store.get("review_access_token")?.value;
  const organizationId = store.get("review_organization_id")?.value;
  if (!token || !organizationId) redirect("/login");
  const workspacePromise = getAIWorkspace(token, organizationId, reviewId);
  const copilotPromise = getAICopilotWorkspace(token, organizationId, reviewId);
  const proposalPromise = query.proposal
    ? getAIProposal(token, organizationId, reviewId, query.proposal)
    : Promise.resolve(null);
  const [workspace, proposal, copilot] = await Promise.all([workspacePromise, proposalPromise, copilotPromise]);
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
        <Link
          className="mt-4 inline-block text-sm font-semibold text-[var(--brand)] hover:underline"
          href={`/reviews/${reviewId}/extraction-ai`}
        >
          Open governed structured extraction &rarr;
        </Link>
      </header>

      {query.error ? <p className="mt-6 rounded-xl bg-red-50 p-4 text-red-800">Request rejected safely.</p> : null}
      {query.updated ? <p className="mt-6 rounded-xl bg-emerald-50 p-4 text-emerald-900">Decision recorded.</p> : null}
      {query.copilot_error ? <p className="mt-6 rounded-xl bg-red-50 p-4 text-red-800">Copilot request rejected safely.</p> : null}
      {query.copilot ? <p className="mt-6 rounded-xl bg-emerald-50 p-4 text-emerald-900">Copilot activity recorded.</p> : null}

      <section className="grid gap-6 border-b border-[var(--line)] py-9 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-2xl border border-[var(--line)] bg-white p-6">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--brand)]">Read-only project intelligence</p>
          <h2 className="mt-2 text-2xl font-semibold">Review copilot</h2>
          <p className="mt-2 text-sm text-[var(--muted)]">
            Ask navigation and workflow-status questions against a bounded snapshot of canonical review metadata. Answers cannot change scientific or workflow state.
          </p>
          <form action={createCopilotQuery.bind(null, reviewId)} className="mt-5">
            <label className="block text-xs font-semibold">Task<select className={field} name="task_key" defaultValue="PROJECT_STATUS">
              {copilot.tasks.map((task) => <option key={task.task_key} value={task.task_key}>{task.label}</option>)}
            </select></label>
            <label className="mt-4 block text-xs font-semibold">Question<textarea className={field} name="copilot_query" required rows={3} placeholder="What is blocking this review?" /></label>
            <button className={`${button} mt-5`} type="submit" disabled={!copilot.policy}>Ask copilot</button>
            {!copilot.policy ? <p className="mt-2 text-xs text-amber-800">A review lead must configure the copilot policy first.</p> : null}
          </form>
        </div>
        <form action={createCopilotPolicy.bind(null, reviewId)} className="rounded-2xl border border-[var(--line)] bg-white p-6">
          <h2 className="text-xl font-semibold">Copilot policy</h2>
          <p className="mt-2 text-sm text-[var(--muted)]">Versioned limits bound query text and canonical context size.</p>
          <label className="mt-4 block text-xs font-semibold">Maximum query characters<input className={field} name="maximum_query_characters" type="number" defaultValue={copilot.policy?.maximum_query_characters ?? 2000} min={100} max={4000} /></label>
          <label className="mt-4 block text-xs font-semibold">Maximum context items<input className={field} name="maximum_context_items" type="number" defaultValue={copilot.policy?.maximum_context_items ?? 50} min={2} max={200} /></label>
          <button className={`${button} mt-5`} type="submit">Save policy version</button>
          {copilot.policy ? <p className="mt-2 text-xs text-[var(--muted)]">Current version: {copilot.policy.version}</p> : null}
        </form>
      </section>

      <section className="border-b border-[var(--line)] py-9">
        <h2 className="text-2xl font-semibold">Copilot activity</h2>
        <div className="mt-5 space-y-3">
          {copilot.queries.map((item) => (
            <article className="rounded-xl border border-[var(--line)] bg-white p-4" key={item.id}>
              <p className="font-semibold">{item.task_key} · {item.status}</p>
              <p className="mt-1 text-sm">{item.query}</p>
              {item.answer?.abstention ? <p className="mt-2 text-sm text-amber-800">Abstained: {item.answer.uncertainty_reason}</p> : item.answer ? <p className="mt-2 text-sm">{item.answer.answer}</p> : null}
              <p className="mt-2 text-xs text-[var(--muted)]">Context hash {item.context_hash} · {item.citations.length} available citations</p>
            </article>
          ))}
          {!copilot.queries.length ? <p className="text-sm text-[var(--muted)]">No copilot queries recorded yet.</p> : null}
        </div>
      </section>

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

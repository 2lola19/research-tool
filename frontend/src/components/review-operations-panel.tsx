import Link from "next/link";
import type { ReactNode } from "react";

import type {
  ReviewOperationsWorkspace,
  ScreeningRound,
  WorkspaceSection,
} from "@/lib/review-workspace-api";

import { adjudicateScreeningOutcome, assignScreeningArticle } from "@/app/reviews/[reviewId]/screening/actions";

const card = "rounded-2xl border border-[var(--line)] bg-white p-6 shadow-[0_14px_45px_rgb(20_35_28/5%)]";
const field = "mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-sm";
const button = "rounded-full bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--brand-deep)]";

const queryMessages: Record<string, string> = {
  assignment_rejected: "The assignment was rejected by the review service.",
  adjudication_rejected: "The adjudication was rejected by the review service.",
  not_authorized: "Your current role cannot perform that operation.",
  service_unavailable: "The operation could not reach the review service. No scientific state was changed.",
};

const successMessages: Record<string, string> = {
  assignment: "The screening assignment was recorded.",
  adjudication: "The screening adjudication was recorded.",
};

function shortId(value: string): string {
  return value.slice(0, 8);
}

function boundedText(value: string, limit = 240): string {
  return value.length > limit ? `${value.slice(0, limit)}…` : value;
}

function formatTimestamp(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "time unavailable" : parsed.toLocaleString();
}

function statusClass(value: string): string {
  if (["COMPLETED", "HEALTHY", "INCLUDE", "CURRENT", "OPEN"].includes(value)) {
    return "bg-emerald-100 text-emerald-900";
  }
  if (["FAILED", "EXPIRED", "ERROR", "CONFLICT", "DEAD_LETTERED"].includes(value)) {
    return "bg-red-100 text-red-900";
  }
  if (["CLOSED", "EXCLUDE", "WARNING", "STALE"].includes(value)) {
    return "bg-amber-100 text-amber-900";
  }
  return "bg-slate-100 text-slate-700";
}

function StatusPill({ value }: { value: string }) {
  return <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusClass(value)}`}>{value.replaceAll("_", " ")}</span>;
}

function SectionState<T>({
  label,
  section,
  children,
}: Readonly<{
  label: string;
  section: WorkspaceSection<T>;
  children: ReactNode;
}>) {
  if (section.status === "ready") return <>{children}</>;
  if (section.status === "not_requested") {
    return <p className="rounded-xl border border-dashed border-[var(--line)] bg-slate-50 p-4 text-sm text-[var(--muted)]">Select a round to load {label.toLowerCase()}.</p>;
  }
  if (section.status === "forbidden") {
    return <p className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900" role="status">{label} are restricted by the server for the current role.</p>;
  }
  return <p className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800" role="alert">{label} are temporarily unavailable. The canonical records are unchanged.</p>;
}

function RoundOption({ round }: { round: ScreeningRound }) {
  return <option value={round.id}>{round.sequence}. {round.name} · {round.stage.replaceAll("_", " ")} · {round.state}</option>;
}

function ReviewHeader({ workspace }: { workspace: ReviewOperationsWorkspace }) {
  return (
    <header className="border-b border-[var(--line)] pb-8">
      <p className="text-xs font-bold uppercase tracking-[0.22em] text-[var(--brand)]">Operational review control plane</p>
      <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-[-0.03em] sm:text-4xl">{workspace.review.title}</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--muted)]">{workspace.review.description ?? "No review description has been added."}</p>
        </div>
        <StatusPill value={workspace.review.archived ? "ARCHIVED" : "ACTIVE"} />
      </div>
      <div className="mt-5 flex flex-wrap gap-x-5 gap-y-2 font-mono text-xs text-[var(--muted)]">
        <span>Slug {workspace.review.project_slug}</span>
        <span>Review {workspace.review.id}</span>
      </div>
    </header>
  );
}

function Notice({ query }: { query: { error?: string; updated?: string } }) {
  const error = query.error ? queryMessages[query.error] : undefined;
  const success = query.updated ? successMessages[query.updated] : undefined;
  return (
    <>
      {error ? <p className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800" role="alert">{error}</p> : null}
      {success ? <p className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900" role="status">{success}</p> : null}
    </>
  );
}

function ScreeningSection({ reviewId, workspace }: { reviewId: string; workspace: ReviewOperationsWorkspace }) {
  const selectedRound = workspace.rounds.data.find((round) => round.id === workspace.selected_round_id);
  const canAssign = workspace.members.status === "ready" && selectedRound?.state === "OPEN";
  return (
    <section className="border-t border-[var(--line)] py-9" id="screening" aria-labelledby="screening-heading">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--brand)]">Human review workflow</p>
          <h2 id="screening-heading" className="mt-2 text-2xl font-semibold">Assignment, queue and quality control</h2>
          <p className="mt-2 max-w-3xl text-sm text-[var(--muted)]">Queues expose only the current reviewer&apos;s authorized assignment data. Consensus and conflict states are calculated and revealed by the API.</p>
        </div>
        <Link className="text-sm font-semibold text-[var(--brand)] hover:underline" href={`/reviews/${reviewId}/screening-ai${workspace.selected_round_id ? `?round=${workspace.selected_round_id}` : ""}`}>Open governed screening assistance &rarr;</Link>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <div className={card}>
          <h3 className="text-xl font-semibold">Screening rounds</h3>
          <p className="mt-2 text-sm text-[var(--muted)]">Rounds remain blinded. Loading a round never reveals peer decisions.</p>
          <SectionState label="Screening rounds" section={workspace.rounds}>
            {workspace.rounds.data.length ? (
              <form action={`/reviews/${reviewId}/screening#screening`} className="mt-5 flex flex-wrap items-end gap-3" method="get">
                <label className="min-w-64 flex-1 text-xs font-semibold" htmlFor="round-selector">
                  Round
                  <select className={field} defaultValue={workspace.selected_round_id ?? ""} id="round-selector" name="round">
                    <option disabled value="">Select a round</option>
                    {workspace.rounds.data.map((round) => <RoundOption key={round.id} round={round} />)}
                  </select>
                </label>
                <button className={button} type="submit">Load queue and QC</button>
              </form>
            ) : <p className="mt-5 rounded-xl border border-dashed border-[var(--line)] p-4 text-sm text-[var(--muted)]">No screening rounds have been created.</p>}
          </SectionState>
          {selectedRound ? (
            <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-3">
              <div><dt className="text-[var(--muted)]">Stage</dt><dd className="mt-1 font-semibold">{selectedRound.stage.replaceAll("_", " ")}</dd></div>
              <div><dt className="text-[var(--muted)]">Decisions/article</dt><dd className="mt-1 font-semibold">{selectedRound.required_decisions}</dd></div>
              <div><dt className="text-[var(--muted)]">Blinding</dt><dd className="mt-1 font-semibold">{selectedRound.blinded ? "Enabled" : "Unavailable"}</dd></div>
            </dl>
          ) : null}
        </div>

        <div className={card}>
          <h3 className="text-xl font-semibold">Review members</h3>
          <p className="mt-2 text-sm text-[var(--muted)]">Assignment controls appear only when the server grants access-management visibility.</p>
          <SectionState label="Review members" section={workspace.members}>
            {workspace.members.data.length ? (
              <ul className="mt-5 space-y-3">
                {workspace.members.data.map((member) => <li className="flex items-start justify-between gap-3 border-b border-[var(--line)] pb-3 text-sm last:border-0 last:pb-0" key={member.user_id}><span><span className="font-semibold">{member.display_name}</span><span className="block text-xs text-[var(--muted)]">{member.email}</span></span><StatusPill value={member.organization_role} /></li>)}
              </ul>
            ) : <p className="mt-5 text-sm text-[var(--muted)]">No review members are visible.</p>}
          </SectionState>
        </div>
      </div>

      {canAssign ? (
        <form action={assignScreeningArticle.bind(null, reviewId)} className={`${card} mt-6`}>
          <h3 className="text-xl font-semibold">Assign an article</h3>
          <p className="mt-2 text-sm text-[var(--muted)]">The server verifies article ownership, duplicate suppression, reviewer permission, review access, and assignment capacity.</p>
          <input name="round_id" type="hidden" value={selectedRound.id} />
          <div className="mt-5 grid gap-4 md:grid-cols-[1fr_1fr_auto] md:items-end">
            <label className="text-xs font-semibold" htmlFor="article-id">Article UUID<input className={field} id="article-id" name="article_id" required spellCheck={false} /></label>
            <label className="text-xs font-semibold" htmlFor="reviewer-id">Reviewer<select className={field} defaultValue="" id="reviewer-id" name="reviewer_user_id" required><option disabled value="">Select a reviewer</option>{workspace.members.data.map((member) => <option key={member.user_id} value={member.user_id}>{member.display_name} · {member.organization_role}</option>)}</select></label>
            <button className={button} type="submit">Assign safely</button>
          </div>
        </form>
      ) : null}

      {workspace.selected_round_id ? (
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <div className={card}>
            <div className="flex items-start justify-between gap-3"><div><h3 className="text-xl font-semibold">Your authorized queue</h3><p className="mt-2 text-sm text-[var(--muted)]">Peer decisions and unrevealed AI content stay withheld.</p></div><span className="rounded-full bg-[#e7f1ec] px-3 py-1 text-sm font-semibold text-[var(--brand-deep)]">{workspace.queue.data.length}</span></div>
            <SectionState label="Queue items" section={workspace.queue}>
              {workspace.queue.data.length ? <ul className="mt-5 space-y-3">{workspace.queue.data.map((item) => <li className="rounded-xl border border-[var(--line)] p-4" key={item.assignment_id}><p className="font-semibold">{item.title}</p><p className="mt-1 font-mono text-xs text-[var(--muted)]">Assignment {shortId(item.assignment_id)} · Article {shortId(item.article_id)}</p><div className="mt-3 flex flex-wrap gap-2"><StatusPill value={item.own_decision ?? "PENDING"} />{item.outcome ? <StatusPill value={item.outcome} /> : <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">Awaiting consensus</span>}</div></li>)}</ul> : <p className="mt-5 rounded-xl border border-dashed border-[var(--line)] p-4 text-sm text-[var(--muted)]">No assignments are available for your role in this round.</p>}
            </SectionState>
          </div>
          <div className={card}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-xl font-semibold">QC outcomes</h3>
                <p className="mt-2 text-sm text-[var(--muted)]">Conflicts require an explicit human adjudication reason.</p>
              </div>
              <span className="rounded-full bg-amber-100 px-3 py-1 text-sm font-semibold text-amber-900">
                {workspace.outcomes.data.filter((item) => item.outcome === "CONFLICT" && !item.adjudication).length} open
              </span>
            </div>
            <SectionState label="QC outcomes" section={workspace.outcomes}>
              {workspace.outcomes.data.length ? (
                <ul className="mt-5 space-y-3">
                  {workspace.outcomes.data.map((item) => (
                    <li className="rounded-xl border border-[var(--line)] p-4" key={item.id}>
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="font-mono text-xs text-[var(--muted)]">Article {shortId(item.article_id)}</span>
                        <div className="flex gap-2">
                          <StatusPill value={item.outcome} />
                          {item.adjudication ? <StatusPill value={`ADJUDICATED_${item.adjudication}`} /> : null}
                        </div>
                      </div>
                      {item.outcome === "CONFLICT" && !item.adjudication ? (
                        <div className="mt-4">
                          <p className="text-sm text-amber-900">Peer decisions conflict. Nothing is finalized until an authorized adjudicator submits a reason.</p>
                          <div className="mt-3 flex flex-wrap gap-2">
                            {(["INCLUDE", "EXCLUDE"] as const).map((decision) => (
                              <form
                                action={adjudicateScreeningOutcome.bind(null, reviewId, item.id, workspace.selected_round_id!, decision)}
                                className="min-w-44 flex-1"
                                key={decision}
                              >
                                <label className="sr-only" htmlFor={`${item.id}-${decision}-reason`}>Reason for {decision.toLowerCase()} adjudication</label>
                                <input className={field} id={`${item.id}-${decision}-reason`} name="reason" placeholder="Adjudication reason" required />
                                <button className={`${button} mt-2 w-full`} type="submit">Adjudicate {decision.toLowerCase()}</button>
                              </form>
                            ))}
                          </div>
                        </div>
                      ) : null}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-5 rounded-xl border border-dashed border-[var(--line)] p-4 text-sm text-[var(--muted)]">No outcomes have been computed for this round.</p>
              )}
            </SectionState>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function WorkflowSection({ workspace }: { workspace: ReviewOperationsWorkspace }) {
  const failedAttempts = workspace.attempts.data.filter((attempt) => ["FAILED", "EXPIRED"].includes(attempt.state));
  const staleReconciliation = workspace.reconciliation.data?.generated_at
    ? new Date(workspace.fetched_at).getTime() - new Date(workspace.reconciliation.data.generated_at).getTime() > 15 * 60 * 1000
    : false;
  return (
    <section className="border-t border-[var(--line)] py-9" id="workflow" aria-labelledby="workflow-heading">
      <div className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--brand)]">Durable operations</p><h2 id="workflow-heading" className="mt-2 text-2xl font-semibold">Jobs, checkpoints and recovery</h2><p className="mt-2 max-w-3xl text-sm text-[var(--muted)]">Worker state is operational metadata. It cannot accept scientific decisions or bypass human checkpoints.</p></div><Link className="text-sm font-semibold text-[var(--brand)] hover:underline" href={`/reviews/${workspace.review.id}/ai`}>Review governed AI runs &rarr;</Link></div>
      {staleReconciliation ? <p className="mt-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900" role="status">The last workflow reconciliation is more than 15 minutes old. Refresh before taking recovery action.</p> : null}
      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <div className={card}><div className="flex items-center justify-between gap-3"><h3 className="text-xl font-semibold">Attempts</h3><span className="rounded-full bg-red-100 px-3 py-1 text-sm font-semibold text-red-900">{failedAttempts.length} errors</span></div><SectionState label="Workflow attempts" section={workspace.attempts}>{workspace.attempts.data.length ? <ul className="mt-5 space-y-3">{workspace.attempts.data.slice(0, 8).map((attempt) => <li className="rounded-xl border border-[var(--line)] p-3" key={attempt.id}><div className="flex items-center justify-between gap-2"><span className="font-mono text-xs">{shortId(attempt.id)} · try {attempt.attempt_number}</span><StatusPill value={attempt.state} /></div>{attempt.failure_code ? <p className="mt-2 text-sm text-red-800">{attempt.failure_code}: {boundedText(attempt.failure_message ?? "No failure detail recorded.")}</p> : null}<p className="mt-2 text-xs text-[var(--muted)]">Worker {attempt.worker_id} · lease until {formatTimestamp(attempt.lease_expires_at)}</p></li>)}</ul> : <p className="mt-5 text-sm text-[var(--muted)]">No workflow attempts recorded.</p>}</SectionState></div>
        <div className={card}><h3 className="text-xl font-semibold">Step checkpoints</h3><SectionState label="Step checkpoints" section={workspace.checkpoints}>{workspace.checkpoints.data.length ? <ul className="mt-5 space-y-3">{workspace.checkpoints.data.map((checkpoint) => <li className="flex items-center justify-between gap-3 border-b border-[var(--line)] pb-3 text-sm last:border-0 last:pb-0" key={checkpoint.id}><span><span className="font-semibold">{checkpoint.step_order}. {checkpoint.step_key}</span><span className="block text-xs text-[var(--muted)]">Version {checkpoint.checkpoint_version}</span></span><StatusPill value={checkpoint.state} /></li>)}</ul> : <p className="mt-5 text-sm text-[var(--muted)]">No step checkpoints recorded.</p>}</SectionState></div>
        <div className={card}><h3 className="text-xl font-semibold">Reconciliation</h3><SectionState label="Workflow reconciliation" section={workspace.reconciliation}>{workspace.reconciliation.data ? <><div className="mt-5 flex items-center justify-between gap-3"><StatusPill value={workspace.reconciliation.data.healthy ? "HEALTHY" : "ERROR"} /><span className="text-xs text-[var(--muted)]">{formatTimestamp(workspace.reconciliation.data.generated_at)}</span></div>{workspace.reconciliation.data.issues.length ? <ul className="mt-5 space-y-3">{workspace.reconciliation.data.issues.map((issue) => <li className="rounded-xl border border-[var(--line)] p-3 text-sm" key={`${issue.code}-${issue.job_id}-${issue.attempt_id ?? "none"}`}><div className="flex items-center justify-between gap-2"><span className="font-mono text-xs">{issue.code}</span><StatusPill value={issue.severity} /></div><p className="mt-2">{issue.message}</p></li>)}</ul> : <p className="mt-5 text-sm text-[var(--muted)]">No reconciliation issues reported.</p>}</> : <p className="mt-5 text-sm text-[var(--muted)]">No reconciliation report available.</p>}</SectionState></div>
      </div>
    </section>
  );
}

function EvidenceSection({ workspace }: { workspace: ReviewOperationsWorkspace }) {
  const summary = workspace.prisma.data;
  return (
    <section className="border-t border-[var(--line)] py-9" aria-labelledby="evidence-heading">
      <div className="flex flex-wrap items-end justify-between gap-4"><div><p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--brand)]">Scientific readiness</p><h2 id="evidence-heading" className="mt-2 text-2xl font-semibold">Evidence status and provenance</h2><p className="mt-2 max-w-3xl text-sm text-[var(--muted)]">Counts and provenance are read from canonical server records. This workspace never recalculates scientific metrics.</p></div><Link className="text-sm font-semibold text-[var(--brand)] hover:underline" href={`/reviews/${workspace.review.id}/reports`}>Open reports and safe downloads &rarr;</Link></div>
      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1fr]">
        <div className={card}><h3 className="text-xl font-semibold">PRISMA readiness</h3><SectionState label="PRISMA summary" section={workspace.prisma}>{summary ? <><div className="mt-5 flex items-center justify-between gap-3"><StatusPill value={summary.readiness.ready_for_final ? "READY" : "DRAFT_ONLY"} /><span className="text-sm text-[var(--muted)]">{summary.readiness.blockers.length} blocker(s)</span></div><dl className="mt-5 grid gap-3 sm:grid-cols-2">{Object.entries(summary.counts).slice(0, 6).map(([key, value]) => <div className="rounded-xl bg-slate-50 p-3" key={key}><dt className="text-xs text-[var(--muted)]">{key.replaceAll("_", " ")}</dt><dd className="mt-1 text-lg font-semibold">{typeof value === "object" ? JSON.stringify(value) : String(value ?? 0)}</dd></div>)}</dl></> : <p className="mt-5 text-sm text-[var(--muted)]">No PRISMA summary is available.</p>}</SectionState></div>
        <div className={card} id="provenance-ledger"><h3 className="text-xl font-semibold">Recent provenance records</h3><SectionState label="Provenance records" section={workspace.provenance}>{workspace.provenance.data.length ? <ul className="mt-5 space-y-3">{workspace.provenance.data.slice(-8).reverse().map((record) => <li className="rounded-xl border border-[var(--line)] p-3 text-sm" key={record.id}><div className="flex flex-wrap items-center justify-between gap-2"><span className="font-semibold">{record.method_name} · v{record.method_version}</span><StatusPill value={record.verification_state} /></div><p className="mt-2 font-mono text-xs text-[var(--muted)]">{record.subject_type} {shortId(record.subject_id)} · source {record.source_type ?? "none"} {record.source_id ? shortId(record.source_id) : ""}</p></li>)}</ul> : <p className="mt-5 text-sm text-[var(--muted)]">No provenance records are visible.</p>}</SectionState></div>
      </div>
    </section>
  );
}

export default function ReviewOperationsPanel({
  reviewId,
  workspace,
  query,
  focus = "overview",
}: Readonly<{
  reviewId: string;
  workspace: ReviewOperationsWorkspace;
  query: { error?: string; updated?: string };
  focus?: "overview" | "screening";
}>) {
  return (
    <main className="mx-auto min-h-screen w-full max-w-7xl px-6 py-8 sm:px-10 lg:px-14">
      <ReviewHeader workspace={workspace} />
      <Notice query={query} />
      <p className="mt-6 rounded-xl border border-sky-200 bg-sky-50 p-4 text-sm text-sky-950" role="status">Live read captured {formatTimestamp(workspace.fetched_at)}. Refresh before consequential recovery or adjudication actions; server authorization and scientific invariants remain authoritative.</p>
      {focus === "overview" ? <><section className="grid gap-4 py-9 sm:grid-cols-2 lg:grid-cols-4" aria-label="Review status summary"><div className={card}><p className="text-sm text-[var(--muted)]">Screening rounds</p><p className="mt-2 text-3xl font-semibold">{workspace.rounds.data.length}</p></div><div className={card}><p className="text-sm text-[var(--muted)]">Queue items</p><p className="mt-2 text-3xl font-semibold">{workspace.queue.status === "ready" ? workspace.queue.data.length : "—"}</p><p className="mt-1 text-xs text-[var(--muted)]">Choose a round below</p></div><div className={card}><p className="text-sm text-[var(--muted)]">Workflow errors</p><p className="mt-2 text-3xl font-semibold">{workspace.attempts.data.filter((attempt) => ["FAILED", "EXPIRED"].includes(attempt.state)).length}</p></div><div className={card}><p className="text-sm text-[var(--muted)]">Provenance records</p><p className="mt-2 text-3xl font-semibold">{workspace.provenance.data.length}</p></div></section><ScreeningSection reviewId={reviewId} workspace={workspace} /><WorkflowSection workspace={workspace} /><EvidenceSection workspace={workspace} /></> : <ScreeningSection reviewId={reviewId} workspace={workspace} />}
    </main>
  );
}

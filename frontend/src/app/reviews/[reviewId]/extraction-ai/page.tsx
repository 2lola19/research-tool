import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";

import { getExtractionAIWorkspace, getExtractionProposal } from "@/lib/ai-extraction-api";

import {
  generateExtractionProposal,
  reviewExtractionField,
  setExtractionPolicy,
} from "./actions";

type Props = {
  params: Promise<{ reviewId: string }>;
  searchParams: Promise<{ assignment?: string; error?: string; updated?: string }>;
};

const field = "mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-sm";
const button = "rounded-full bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white";

function displayValue(value: unknown): string {
  return typeof value === "string" ? value : JSON.stringify(value);
}

export default async function ExtractionAIPage({ params, searchParams }: Props) {
  const [{ reviewId }, query, store] = await Promise.all([params, searchParams, cookies()]);
  const token = store.get("review_access_token")?.value;
  const organizationId = store.get("review_organization_id")?.value;
  if (!token || !organizationId) redirect("/login");
  const [workspace, proposal] = await Promise.all([
    getExtractionAIWorkspace(token, organizationId, reviewId),
    query.assignment
      ? getExtractionProposal(token, organizationId, reviewId, query.assignment)
      : Promise.resolve(null),
  ]);
  if (workspace.status === "unauthorized") redirect("/login?error=session_expired");
  const fieldValidation = new Map(
    (proposal?.validation_results?.field_results ?? []).map((item) => [item.field_id, item]),
  );

  return (
    <main className="mx-auto min-h-screen w-full max-w-7xl px-6 py-8 sm:px-10 lg:px-14">
      <header className="border-b border-[var(--line)] pb-7">
        <Link className="text-sm font-semibold text-[var(--brand)] hover:underline" href={`/reviews/${reviewId}/ai`}>
          &larr; AI workspace
        </Link>
        <p className="mt-6 text-xs font-bold uppercase tracking-[0.22em] text-[var(--brand)]">
          Schema-pinned, document-grounded, human-only acceptance
        </p>
        <h1 className="mt-2 text-3xl font-semibold">AI structured extraction</h1>
        <p className="mt-2 max-w-4xl text-sm text-[var(--muted)]">
          Suggestions are immutable advisory records. Only your normal human extraction submission
          can become canonical or enter verification, harmonization, and analysis.
        </p>
      </header>

      {query.error ? <p className="mt-6 rounded-xl bg-red-50 p-4 text-red-800" role="alert">The request was rejected safely.</p> : null}
      {query.updated ? <p className="mt-6 rounded-xl bg-emerald-50 p-4 text-emerald-900" role="status">Extraction AI workspace updated.</p> : null}

      <section className="grid gap-6 py-9 lg:grid-cols-2">
        <form action={setExtractionPolicy.bind(null, reviewId)} className="rounded-2xl border border-[var(--line)] bg-white p-6">
          <h2 className="text-xl font-semibold">Assistance policy</h2>
          <select className={field} defaultValue="ASSISTED" name="mode">
            <option value="OFF">Off</option>
            <option value="BLINDED_AI">Blinded AI</option>
            <option value="ASSISTED">Assisted</option>
          </select>
          <label className="mt-4 block text-xs font-semibold">Maximum batch size<input className={field} defaultValue="20" max="100" min="1" name="maximum_batch_size" type="number" /></label>
          <button className={`${button} mt-5`} type="submit">Save versioned policy</button>
        </form>
        <form action={generateExtractionProposal.bind(null, reviewId)} className="rounded-2xl border border-[var(--line)] bg-white p-6">
          <h2 className="text-xl font-semibold">Generate bounded proposal</h2>
          <label className="mt-4 block text-xs font-semibold">Human extraction assignment UUID<input className={field} name="assignment_id" required /></label>
          <label className="mt-4 block text-xs font-semibold">Allowed document UUIDs<input className={field} name="document_ids" placeholder="primary, supplement" required /></label>
          <p className="mt-2 text-xs text-[var(--muted)]">The first document is primary full text; additional documents are explicit supplements.</p>
          <button className={`${button} mt-5`} type="submit">Generate governed extraction proposal</button>
        </form>
      </section>

      <section className="border-t border-[var(--line)] py-9">
        <h2 className="text-2xl font-semibold">Field review</h2>
        {!proposal ? (
          <div className="mt-5 space-y-3">
            <p className="rounded-xl border border-dashed border-[var(--line)] p-4 text-sm">Select a recent assignment below or generate a proposal.</p>
            {workspace.proposals.map((item) => (
              <Link className="block rounded-xl border border-[var(--line)] bg-white p-4 hover:border-[var(--brand)]" href={`/reviews/${reviewId}/extraction-ai?assignment=${item.assignment_id}`} key={item.assignment_id}>
                <span className="font-semibold">Assignment {item.assignment_id}</span>
                <span className="ml-2 text-xs text-[var(--muted)]">{item.mode} · {item.status} · {item.readiness}</span>
              </Link>
            ))}
          </div>
        ) : (
          <div className="mt-5">
            <div className="flex flex-wrap gap-2 text-xs font-semibold">
              <span className="rounded-full bg-slate-100 px-3 py-1">{proposal.mode}</span>
              <span className="rounded-full bg-slate-100 px-3 py-1">{proposal.readiness}</span>
              <span className={`rounded-full px-3 py-1 ${proposal.stale ? "bg-red-50 text-red-800" : "bg-emerald-50 text-emerald-900"}`}>{proposal.stale ? "STALE" : "CURRENT"}</span>
              <span className="rounded-full bg-slate-100 px-3 py-1">Schema {proposal.schema_version_id}</span>
            </div>
            <p className="mt-3 text-xs text-[var(--muted)]">{proposal.selection_method}; {proposal.selected_chunk_ids.length} selected, {proposal.omitted_chunk_count} omitted. {proposal.stale_reasons.join(", ")}</p>
            <div className="mt-4 grid gap-2 text-xs sm:grid-cols-2">
              {proposal.source_manifest.map((source) => (
                <div className="rounded-lg bg-slate-50 p-3" key={source.document_id}>
                  <p className="font-semibold">{source.document_role} · Article {source.article_id}</p>
                  <p className="break-all">Document {source.document_id}</p>
                  <p>{source.parser_name} {source.parser_version}</p>
                </div>
              ))}
            </div>
            {!proposal.is_revealed ? (
              <p className="mt-5 rounded-xl bg-amber-50 p-4 text-sm text-amber-900">An AI proposal exists. Values, missingness, confidence, evidence, and validation are withheld server-side until the assigned human extraction is submitted.</p>
            ) : (
              <div className="mt-6 space-y-5">
                {(proposal.structured_value?.fields ?? []).map((item) => {
                  const validation = fieldValidation.get(item.field_id);
                  return (
                    <article className="rounded-2xl border border-[var(--line)] bg-white p-5" key={item.field_id}>
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div><h3 className="font-semibold">{item.field_id}</h3><p className="text-sm">{item.status}: {displayValue(item.value)}</p><p className="text-xs text-[var(--muted)]">Reported: {item.reported_value ?? "none"} · Unit: {item.unit ?? "none"} · Confidence: {item.confidence ?? "not reported"}</p></div>
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${validation?.valid ? "bg-emerald-50 text-emerald-900" : "bg-red-50 text-red-800"}`}>{validation?.valid ? "VALID" : "INVALID"}</span>
                      </div>
                      {(validation?.errors ?? []).map((error) => <p className="mt-2 text-xs text-red-800" key={error}>{error}</p>)}
                      <div className="mt-4 space-y-3">
                        {item.evidence.map((span) => <blockquote className="rounded-xl border-l-4 border-[var(--brand)] bg-slate-50 p-4 text-sm" key={`${span.chunk_id}-${span.quote}`}><p className="text-xs font-semibold text-[var(--muted)]">Document {span.document_id} · {span.page == null ? "page unavailable" : `page ${span.page}`} · {span.section ?? "section unavailable"}{span.table_id ? ` · table ${span.table_id}` : ""}</p><p className="mt-2">“{span.quote}”</p></blockquote>)}
                      </div>
                      {proposal.mode === "ASSISTED" && proposal.proposal_id && !proposal.stale ? (
                        <div className="mt-4 flex flex-wrap gap-3">
                          {(["ACCEPTED", "REJECTED", "UNRESOLVED"] as const).map((action) => <form action={reviewExtractionField.bind(null, reviewId, proposal.proposal_id!, item.field_id, proposal.assignment_id, action)} key={action}><input className={field} name="reason" placeholder="Reason (optional)" /><button className={`${button} mt-2`} disabled={action === "ACCEPTED" && !validation?.valid} type="submit">{action}</button></form>)}
                          <form action={reviewExtractionField.bind(null, reviewId, proposal.proposal_id, item.field_id, proposal.assignment_id, "EDITED")}><textarea className={field} name="human_value" placeholder='Human canonical value JSON, e.g. {"value":146,"missingness":"VALUE_REPORTED"}' required rows={3} /><input className={field} name="reason" placeholder="Edit reason" required /><button className={`${button} mt-2`} type="submit">EDITED</button></form>
                        </div>
                      ) : null}
                    </article>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </section>

      <section className="border-t border-[var(--line)] py-9 text-sm">
        <h2 className="text-xl font-semibold">Evaluation safety</h2>
        <p className="mt-2 text-[var(--muted)]">Field-level reference datasets, grounding metrics, calibration bins, simulation-only thresholds, and high-risk hallucination queues are separate from scientific results. No threshold can enable automatic acceptance.</p>
        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          {workspace.datasets.map((dataset) => <article className="rounded-xl border border-[var(--line)] bg-white p-4" key={dataset.id}><p className="font-semibold">{dataset.name} v{dataset.version}</p><p className="text-xs text-[var(--muted)]">{dataset.reference_standard} · schema {dataset.schema_version_id}</p></article>)}
          {workspace.evaluations.map((evaluation) => <article className="rounded-xl border border-[var(--line)] bg-white p-4" key={evaluation.id}><p className="font-semibold">Evaluation {evaluation.id}</p><pre className="mt-2 overflow-auto rounded-lg bg-slate-950 p-3 text-xs text-slate-100">{JSON.stringify(evaluation.metrics, null, 2)}</pre></article>)}
        </div>
        <h3 className="mt-6 font-semibold text-red-800">High-risk field results ({workspace.highRisk.length})</h3>
        <div className="mt-3 space-y-3">{workspace.highRisk.map((item) => <article className="rounded-xl border border-red-200 bg-red-50 p-4" key={item.id}><p className="font-semibold">{item.classification} · {item.error_categories.join(", ")}</p><p className="mt-1">AI: {displayValue(item.ai_value)} · Reference: {displayValue(item.reference_value)}</p><p className="text-xs">Evidence valid: {String(item.evidence_valid)} · proposal {item.proposal_id ?? "none"}</p>{item.source_location ? <pre className="mt-2 overflow-auto text-xs">{JSON.stringify(item.source_location, null, 2)}</pre> : null}</article>)}</div>
      </section>
    </main>
  );
}

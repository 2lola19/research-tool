import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";

import {
  getFullTextAIWorkspace,
  getFullTextSuggestion,
} from "@/lib/ai-full-text-screening-api";

import {
  acceptFullTextSuggestion,
  createFullTextDataset,
  evaluateFullTextDataset,
  generateFullTextSuggestion,
} from "./actions";

type Props = {
  params: Promise<{ reviewId: string }>;
  searchParams: Promise<{ assignment?: string; error?: string; updated?: string }>;
};

type HighRiskDisagreement = {
  proposal_id?: string;
  article_id?: string;
  document_id?: string;
  confidence?: number;
  reference_decision?: string;
  ai_suggestion?: string;
  ai_criterion_ids?: string[];
  citation?: { title?: string };
  evidence?: Array<{
    chunk_id?: string;
    page?: number | null;
    section?: string | null;
    quoted_text?: string;
  }>;
};

const field = "mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-sm";
const button = "rounded-full bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white";

function percentage(value: unknown): string {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "n/a";
}

export default async function FullTextAIPage({ params, searchParams }: Props) {
  const [{ reviewId }, query, store] = await Promise.all([params, searchParams, cookies()]);
  const token = store.get("review_access_token")?.value;
  const organizationId = store.get("review_organization_id")?.value;
  if (!token || !organizationId) redirect("/login");
  const [workspace, suggestion] = await Promise.all([
    getFullTextAIWorkspace(token, organizationId, reviewId),
    query.assignment
      ? getFullTextSuggestion(token, organizationId, reviewId, query.assignment)
      : Promise.resolve(null),
  ]);
  const evidence = suggestion?.structured_value?.evidence ?? [];
  const metrics = workspace.evaluations[0]?.metrics;
  const grounding = metrics?.evidence_grounding as Record<string, unknown> | undefined;
  const criterion = metrics?.criterion_level as Record<string, unknown> | undefined;
  const highRisk = Array.isArray(metrics?.high_risk_disagreements)
    ? (metrics.high_risk_disagreements as HighRiskDisagreement[])
    : [];
  const caseResultsByProposal = new Map(
    workspace.caseResults.map((item) => [item.proposal_id, item] as const),
  );

  return (
    <main className="mx-auto min-h-screen w-full max-w-7xl px-6 py-8 sm:px-10 lg:px-14">
      <header className="border-b border-[var(--line)] pb-7">
        <Link
          className="text-sm font-semibold text-[var(--brand)] hover:underline"
          href={`/reviews/${reviewId}/screening-ai`}
        >
          &larr; Title/abstract AI
        </Link>
        <p className="mt-6 text-xs font-bold uppercase tracking-[0.22em] text-[var(--brand)]">
          Document-grounded eligibility assistance
        </p>
        <h1 className="mt-2 text-3xl font-semibold">AI full-text screening</h1>
        <p className="mt-2 max-w-4xl text-sm text-[var(--muted)]">
          The selected document version and parser representation are pinned. Suggestions never
          change canonical screening or PRISMA; an authorized human must decide through the normal
          screening service.
        </p>
      </header>

      {query.error ? (
        <p className="mt-6 rounded-xl bg-red-50 p-4 text-red-800" role="alert">
          The full-text request was rejected safely. Check assignment, document readiness, policy,
          and protocol.
        </p>
      ) : null}
      {query.updated ? (
        <p className="mt-6 rounded-xl bg-emerald-50 p-4 text-emerald-900" role="status">
          Full-text AI workspace updated.
        </p>
      ) : null}

      <section className="grid gap-6 py-9 lg:grid-cols-[0.9fr_1.4fr]">
        <form
          action={generateFullTextSuggestion.bind(null, reviewId)}
          className="rounded-2xl border border-[var(--line)] bg-white p-6"
        >
          <h2 className="text-xl font-semibold">Generate bounded suggestion</h2>
          <p className="mt-2 text-sm text-[var(--muted)]">
            One independent run is created per assignment. Missing or unreadable full text blocks
            execution before provider invocation.
          </p>
          {[
            ["assignment_id", "Full-text assignment UUID"],
            ["document_id", "Processed document UUID"],
            ["protocol_version_id", "Approved protocol UUID (optional)"],
          ].map(([name, label]) => (
            <label className="mt-4 block text-xs font-semibold" key={name}>
              {label}
              <input className={field} name={name} required={name !== "protocol_version_id"} />
            </label>
          ))}
          <label className="mt-4 block text-xs font-semibold">
            Document role
            <select className={field} defaultValue="PRIMARY_FULL_TEXT" name="document_role">
              <option value="PRIMARY_FULL_TEXT">Primary full text</option>
              <option value="SUPPLEMENT">Supplement</option>
              <option value="APPENDIX">Appendix</option>
              <option value="OTHER_SUPPORTING_DOCUMENT">Other supporting document</option>
            </select>
          </label>
          <button className={`${button} mt-5`} type="submit">
            Generate governed full-text suggestion
          </button>
        </form>

        <div className="rounded-2xl border border-[var(--line)] bg-white p-6">
          <h2 className="text-xl font-semibold">Assignment proposal</h2>
          {!suggestion ? (
            <p className="mt-4 rounded-xl border border-dashed border-[var(--line)] p-5 text-sm">
              Add <code>?assignment=...</code> or generate a proposal to inspect an authorized
              assignment.
            </p>
          ) : (
            <>
              <div className="mt-4 flex flex-wrap gap-2 text-xs font-semibold">
                <span className="rounded-full bg-slate-100 px-3 py-1">{suggestion.mode}</span>
                <span className="rounded-full bg-slate-100 px-3 py-1">
                  Readiness {suggestion.readiness}
                </span>
                {suggestion.stale ? (
                  <span className="rounded-full bg-red-50 px-3 py-1 text-red-800">STALE</span>
                ) : (
                  <span className="rounded-full bg-emerald-50 px-3 py-1 text-emerald-900">
                    Current inputs
                  </span>
                )}
              </div>
              <dl className="mt-5 grid gap-2 text-xs sm:grid-cols-2">
                <div>
                  <dt className="text-[var(--muted)]">Document version</dt>
                  <dd className="break-all font-mono">{suggestion.document_version_id}</dd>
                </div>
                <div>
                  <dt className="text-[var(--muted)]">Parser run</dt>
                  <dd className="break-all font-mono">{suggestion.processing_run_id}</dd>
                </div>
              </dl>
              {!suggestion.is_revealed ? (
                <p className="mt-5 rounded-xl bg-amber-50 p-4 text-sm text-amber-900">
                  Proposal content is withheld server-side until the human full-text decision.
                </p>
              ) : (
                <div className="mt-5">
                  <p className="text-2xl font-semibold">{suggestion.suggestion}</p>
                  <p className="mt-2 text-sm">{suggestion.structured_value?.rationale}</p>
                  <p className="mt-2 text-xs text-[var(--muted)]">
                    Confidence is model-reported and not assumed calibrated: {" "}
                    {percentage(suggestion.structured_value?.model_reported_confidence)}
                  </p>
                  {(suggestion.structured_value?.missing_information ?? []).length > 0 ? (
                    <p className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
                      Missing information: {suggestion.structured_value?.missing_information?.join(", ")}
                    </p>
                  ) : null}
                  <div className="mt-5 space-y-3">
                    {evidence.map((item) => (
                      <blockquote
                        className="rounded-xl border-l-4 border-[var(--brand)] bg-slate-50 p-4 text-sm"
                        key={`${item.chunk_id}-${item.quoted_text}`}
                      >
                        <p className="text-xs font-semibold text-[var(--muted)]">
                          {item.page === null ? "Page unavailable" : `Page ${item.page}`} · {item.section ?? "Section unavailable"}
                        </p>
                        <p className="mt-2">“{item.quoted_text}”</p>
                      </blockquote>
                    ))}
                  </div>
                  {suggestion.proposal_id && !suggestion.stale && ["INCLUDE", "EXCLUDE"].includes(suggestion.suggestion ?? "") ? (
                    <form
                      action={acceptFullTextSuggestion.bind(
                        null,
                        reviewId,
                        suggestion.proposal_id,
                        suggestion.assignment_id,
                      )}
                      className="mt-5"
                    >
                      <input
                        className={field}
                        name="exclusion_reason"
                        placeholder="Human canonical exclusion reason (when excluding)"
                      />
                      <button className={`${button} mt-3`} type="submit">
                        Use suggestion as my human decision
                      </button>
                    </form>
                  ) : null}
                </div>
              )}
            </>
          )}
        </div>
      </section>

      <section className="grid gap-6 border-t border-[var(--line)] py-9 lg:grid-cols-2">
        <div>
          <h2 className="text-2xl font-semibold">Full-text reference datasets</h2>
          <form
            action={createFullTextDataset.bind(null, reviewId)}
            className="mt-5 rounded-xl border border-[var(--line)] bg-white p-4"
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <input className={field} name="logical_key" placeholder="Logical key" required />
              <input className={field} name="name" placeholder="Dataset name" required />
              <input className={field} name="document_id" placeholder="Document UUID" required />
              <input className={field} name="protocol_version_id" placeholder="Protocol UUID" />
              <select className={field} defaultValue="RETAIN" name="reference_decision">
                <option value="RETAIN">Reference: retain</option>
                <option value="EXCLUDE">Reference: exclude</option>
              </select>
              <input
                className={field}
                name="reference_criterion_id"
                placeholder="Criterion ID for exclusion"
              />
            </div>
            <button className={`${button} mt-4`} type="submit">
              Save curated full-text case
            </button>
          </form>
          <div className="mt-5 space-y-3">
            {workspace.datasets.map((dataset) => (
              <article className="rounded-xl border border-[var(--line)] bg-white p-4" key={dataset.id}>
                <p className="font-semibold">{dataset.name} v{dataset.version}</p>
                <p className="mt-1 text-xs text-[var(--muted)]">{dataset.reference_standard} · FULL_TEXT</p>
                <form action={evaluateFullTextDataset.bind(null, reviewId, dataset.id)}>
                  <button className={`${button} mt-3`} type="submit">Run evaluation</button>
                </form>
              </article>
            ))}
          </div>
        </div>

        <div>
          <h2 className="text-2xl font-semibold">Safety evaluation</h2>
          {!metrics ? (
            <p className="mt-5 rounded-xl border border-dashed border-[var(--line)] p-4 text-sm">
              No full-text evaluation yet.
            </p>
          ) : (
            <div className="mt-5 rounded-xl border border-[var(--line)] bg-white p-5">
              <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
                <div><dt className="text-[var(--muted)]">Sensitivity</dt><dd className="font-semibold">{percentage(metrics.sensitivity)}</dd></div>
                <div><dt className="text-[var(--muted)]">False-negative rate</dt><dd className="font-semibold">{percentage(metrics.false_negative_rate)}</dd></div>
                <div><dt className="text-[var(--muted)]">Specificity</dt><dd className="font-semibold">{percentage(metrics.specificity)}</dd></div>
                <div><dt className="text-[var(--muted)]">Abstention</dt><dd className="font-semibold">{percentage(metrics.abstention_rate)}</dd></div>
                <div><dt className="text-[var(--muted)]">Evidence validity</dt><dd className="font-semibold">{percentage(grounding?.evidence_validation_rate)}</dd></div>
                <div><dt className="text-[var(--muted)]">Criterion accuracy</dt><dd className="font-semibold">{percentage(criterion?.criterion_accuracy)}</dd></div>
              </dl>
              <p className="mt-5 text-xs font-semibold text-red-800">
                High-risk AI EXCLUDE / human INCLUDE disagreements: {highRisk.length}
              </p>
              <div className="mt-3 space-y-3">
                {highRisk.map((item) => (
                  <article
                    className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm"
                    key={`${item.article_id}-${item.document_id}`}
                  >
                    <p className="font-semibold">
                      {item.citation?.title ?? item.article_id ?? "Unknown citation"}
                    </p>
                    <p className="mt-1 break-all text-xs text-red-900">
                      Document {item.document_id ?? "unknown"} · AI confidence {percentage(item.confidence)}
                      {" · "}AI {item.ai_suggestion ?? "EXCLUDE"}
                      {" · "}Reference {item.reference_decision ?? "RETAIN"}
                    </p>
                    <p className="mt-1 text-xs text-red-900">
                      AI criteria: {item.ai_criterion_ids?.join(", ") || "none"}
                    </p>
                    {(caseResultsByProposal.get(String(item.proposal_id))?.error_classifications ?? [])
                      .map((classification) => (
                        <p className="mt-1 text-xs font-semibold text-red-900" key={classification.category}>
                          Error classification: {classification.category}
                          {classification.notes ? ` · ${classification.notes}` : ""}
                        </p>
                      ))}
                    {(item.evidence ?? []).map((evidenceItem) => (
                      <blockquote
                        className="mt-3 border-l-2 border-red-400 pl-3"
                        key={evidenceItem.chunk_id}
                      >
                        <p className="text-xs font-semibold">
                          {evidenceItem.page == null ? "Page unavailable" : `Page ${evidenceItem.page}`}
                          {" · "}{evidenceItem.section ?? "Section unavailable"}
                        </p>
                        <p className="mt-1">“{evidenceItem.quoted_text}”</p>
                      </blockquote>
                    ))}
                  </article>
                ))}
              </div>
              <p className="mt-2 text-xs text-[var(--muted)]">
                Threshold results are simulations only and never activate automatic exclusion.
              </p>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}

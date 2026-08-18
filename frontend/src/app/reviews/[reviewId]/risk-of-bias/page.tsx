import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { getRiskOfBiasWorkspace } from "@/lib/api";
import { getAIRiskOfBiasWorkspace } from "@/lib/ai-risk-of-bias-api";

import {
  adjudicateComparison,
  createAIRiskOfBiasPolicy,
  compareAssessments,
  createAssessment,
  decideVersion,
  generateAIRiskOfBiasProposal,
  installDemonstration,
  reviewAIRiskOfBiasAnswer,
  saveAnswer,
  saveDomain,
  saveOverall,
  submitAssessment,
} from "./actions";

type Props = {
  params: Promise<{ reviewId: string }>;
  searchParams: Promise<{ error?: string; updated?: string }>;
};

const field =
  "mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-sm";
const button =
  "rounded-full bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white";

export default async function RiskOfBiasPage({ params, searchParams }: Props) {
  const [{ reviewId }, query, cookieStore] = await Promise.all([params, searchParams, cookies()]);
  const accessToken = cookieStore.get("review_access_token")?.value;
  const organizationId = cookieStore.get("review_organization_id")?.value;
  if (!accessToken || !organizationId) redirect("/login");
  const [result, aiResult] = await Promise.all([
    getRiskOfBiasWorkspace(accessToken, organizationId, reviewId),
    getAIRiskOfBiasWorkspace(accessToken, organizationId, reviewId),
  ]);
  if (result.status === "unauthorized") redirect("/login?error=session_expired");

  const versions = result.instruments.flatMap((instrument) => instrument.versions);
  const approvedVersions = versions.filter((version) => version.decision === "APPROVED");
  const versionById = Object.fromEntries(versions.map((version) => [version.id, version]));
  const studyById = Object.fromEntries(result.studies.map((study) => [study.id, study]));
  const submitted = result.assessments.filter((assessment) => assessment.status === "SUBMITTED");

  return (
    <main className="mx-auto min-h-screen w-full max-w-7xl px-6 py-8 sm:px-10 lg:px-14">
      <header className="border-b border-[var(--line)] pb-7">
        <Link className="text-sm font-semibold text-[var(--brand)] hover:underline" href="/reviews">
          &larr; Review projects
        </Link>
        <p className="mt-6 text-xs font-bold uppercase tracking-[0.22em] text-[var(--brand)]">
          Structured scientific appraisal
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-[-0.03em]">Risk of Bias</h1>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Independent, instrument-pinned Study assessments with explicit evidence and adjudication.
        </p>
      </header>

      {query.error ? (
        <p className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          The scientific write was not accepted ({query.error.replaceAll("_", " ")}).
        </p>
      ) : null}
      {query.updated ? (
        <p className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
          {query.updated.replaceAll("_", " ")}.
        </p>
      ) : null}

      <section className="mt-8 grid gap-6 border-y border-[var(--line)] py-8 lg:grid-cols-[1fr_1.4fr]">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--brand)]">
            Governed assistance
          </p>
          <h2 className="mt-2 text-2xl font-semibold">Risk of Bias AI assistant</h2>
          <p className="mt-2 text-sm text-[var(--muted)]">
            The assistant proposes only instrument-allowed signalling answers. It never submits
            an assessment, replaces dual human review, adjudicates disagreement, or creates a
            domain or overall judgment.
          </p>
          <form action={createAIRiskOfBiasPolicy.bind(null, reviewId)} className="mt-5 space-y-3 rounded-xl bg-[#edf4f0] p-4">
            <label className="block text-xs font-semibold">Assistance mode
              <select className={field} defaultValue="BLINDED_AI" name="mode">
                <option value="BLINDED_AI">Blinded until submission</option>
                <option value="ASSISTED">Assisted reviewer view</option>
              </select>
            </label>
            <label className="block text-xs font-semibold">Maximum batch size
              <input className={field} defaultValue="20" min="1" max="100" name="maximum_batch_size" type="number" />
            </label>
            <button className={button} type="submit">Save governed policy</button>
          </form>
        </div>
        <div>
          <form action={generateAIRiskOfBiasProposal.bind(null, reviewId)} className="rounded-xl border border-[var(--line)] bg-white p-5">
            <h3 className="font-semibold">Prepare a document-grounded proposal</h3>
            <p className="mt-1 text-xs text-[var(--muted)]">Enter the assigned assessment and one or more processed Document UUIDs. The first is treated as primary full text; later IDs are explicit supplements.</p>
            <label className="mt-4 block text-xs font-semibold">Assessment UUID
              <input className={field} name="assessment_id" placeholder="Assessment UUID" required />
            </label>
            <label className="mt-4 block text-xs font-semibold">Processed Document UUIDs
              <textarea className={field} name="document_ids" placeholder="Document UUIDs separated by spaces or commas" required />
            </label>
            <button className={`${button} mt-4`} type="submit">Generate proposal</button>
          </form>
          {aiResult.status === "unavailable" ? <p className="mt-3 text-sm text-amber-800">AI assistance data is temporarily unavailable; canonical assessment data is unaffected.</p> : null}
          {aiResult.status === "unauthorized" ? <p className="mt-3 text-sm text-[var(--muted)]">AI assistance is restricted to authorized review roles.</p> : null}
        </div>
      </section>

      {result.status === "unavailable" ? (
        <section className="mt-8 rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-900">
          The Risk of Bias service is unavailable. No scientific record was changed.
        </section>
      ) : (
        <>
          <section className="grid gap-6 py-9 lg:grid-cols-2">
            <div className="rounded-2xl border border-[var(--line)] bg-white p-6">
              <h2 className="text-xl font-semibold">Instrument library</h2>
              <p className="mt-2 text-sm text-[var(--muted)]">
                The bundled RCT instrument validates the framework only; it is not complete RoB 2.
              </p>
              {result.instruments.length === 0 ? (
                <form action={installDemonstration.bind(null, reviewId)} className="mt-5">
                  <button className={button} type="submit">Install demonstration instrument</button>
                </form>
              ) : (
                <ul className="mt-5 space-y-3">
                  {result.instruments.map((instrument) => (
                    <li className="rounded-xl border border-[var(--line)] p-4" key={instrument.id}>
                      <p className="font-semibold">{instrument.name}</p>
                      <p className="mt-1 text-xs text-[var(--muted)]">{instrument.description}</p>
                      {instrument.versions.map((version) => (
                        <div className="mt-3 flex items-center justify-between gap-3" key={version.id}>
                          <span className="font-mono text-xs">
                            v{version.version} &middot; {version.decision ?? "PENDING"}
                          </span>
                          {version.decision === null ? (
                            <div className="flex gap-2">
                              <form action={decideVersion.bind(null, reviewId, version.id, "APPROVED")}>
                                <button className="text-sm font-semibold text-[var(--brand)]" type="submit">Approve</button>
                              </form>
                              <form action={decideVersion.bind(null, reviewId, version.id, "REJECTED")}>
                                <button className="text-sm font-semibold text-red-700" type="submit">Reject</button>
                              </form>
                            </div>
                          ) : null}
                        </div>
                      ))}
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <form action={createAssessment.bind(null, reviewId)} className="rounded-2xl border border-[var(--line)] bg-white p-6">
              <h2 className="text-xl font-semibold">Start independent assessment</h2>
              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                <label className="text-sm font-semibold">Study
                  <select className={field} name="study_id" required>
                    <option value="">Select Study</option>
                    {result.studies.map((study) => (
                      <option key={study.id} value={study.id}>{study.study_key} &middot; {study.study_design ?? "design missing"}</option>
                    ))}
                  </select>
                </label>
                <label className="text-sm font-semibold">Approved instrument
                  <select className={field} name="instrument_version_id" required>
                    <option value="">Select version</option>
                    {approvedVersions.map((version) => (
                      <option key={version.id} value={version.id}>{version.definition.name} v{version.version}</option>
                    ))}
                  </select>
                </label>
                <label className="text-sm font-semibold">Assessment round
                  <input className={field} defaultValue="1" min="1" name="round_number" type="number" />
                </label>
              </div>
              <button className={`${button} mt-5`} type="submit">Create assessment</button>
            </form>
          </section>

          <section className="border-t border-[var(--line)] py-9">
            <h2 className="text-2xl font-semibold">Assessment workspace</h2>
            <div className="mt-6 space-y-6">
              {result.assessments.map((assessment) => {
                const version = versionById[assessment.instrument_version_id];
                const study = studyById[assessment.study_id];
                return (
                  <article className="rounded-2xl border border-[var(--line)] bg-white p-6" key={assessment.id}>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h3 className="text-lg font-semibold">{study?.label ?? study?.study_key ?? assessment.study_id}</h3>
                        <p className="mt-1 font-mono text-xs text-[var(--muted)]">Round {assessment.round_number} &middot; revision {assessment.revision} &middot; {assessment.status}</p>
                      </div>
                      <span className="rounded-full bg-[#edf4f0] px-3 py-1 text-xs font-semibold">{assessment.overall_final_judgment ?? "No overall judgment"}</span>
                    </div>
                    {assessment.status === "IN_PROGRESS" && version ? (
                      <div className="mt-6 space-y-6">
                        {version.definition.domains.map((domain) => (
                          <section className="rounded-xl border border-[var(--line)] p-4" key={domain.key}>
                            <h4 className="font-semibold">{domain.label}</h4>
                            {domain.questions.map((question) => (
                              <form action={saveAnswer.bind(null, reviewId, assessment.id, question.key)} className="mt-4 grid gap-3 sm:grid-cols-[1fr_10rem_1fr_1fr_auto] sm:items-end" key={question.key}>
                                <p className="text-sm">{question.text}</p>
                                <label className="text-xs font-semibold">Answer
                                  <select className={field} name="answer" required>
                                    {question.allowed_answers.map((choice) => <option key={choice}>{choice}</option>)}
                                  </select>
                                </label>
                                <label className="text-xs font-semibold">Rationale
                                  <input className={field} name="rationale" />
                                </label>
                                <label className="text-xs font-semibold">Evidence location ID
                                  <input className={field} name="evidence_location_id" />
                                </label>
                                <button className="text-sm font-semibold text-[var(--brand)]" type="submit">Save</button>
                              </form>
                            ))}
                            <form action={saveDomain.bind(null, reviewId, assessment.id, domain.key)} className="mt-5 grid gap-3 border-t border-[var(--line)] pt-4 sm:grid-cols-4">
                              <label className="text-xs font-semibold">Domain judgment
                                <select className={field} name="final_judgment" required>
                                  {version.definition.domain_judgment_choices.map((choice) => <option key={choice.value} value={choice.value}>{choice.label}</option>)}
                                </select>
                              </label>
                              <label className="text-xs font-semibold">Rationale
                                <input className={field} name="rationale" required />
                              </label>
                              <label className="text-xs font-semibold">Override reason (if needed)
                                <input className={field} name="override_reason" />
                              </label>
                              <label className="text-xs font-semibold">Evidence location ID
                                <input className={field} name="evidence_location_id" />
                              </label>
                              <button className="text-left text-sm font-semibold text-[var(--brand)]" type="submit">Save domain judgment</button>
                            </form>
                          </section>
                        ))}
                        <form action={saveOverall.bind(null, reviewId, assessment.id)} className="grid gap-3 rounded-xl bg-[#edf4f0] p-4 sm:grid-cols-4">
                          <label className="text-xs font-semibold">Overall judgment
                            <select className={field} name="final_judgment" required>
                              {version.definition.overall_judgment_choices.map((choice) => <option key={choice.value} value={choice.value}>{choice.label}</option>)}
                            </select>
                          </label>
                          <label className="text-xs font-semibold">Rationale
                            <input className={field} name="rationale" required />
                          </label>
                          <label className="text-xs font-semibold">Override reason (if needed)
                            <input className={field} name="override_reason" />
                          </label>
                          <label className="text-xs font-semibold">Evidence location ID
                            <input className={field} name="evidence_location_id" />
                          </label>
                          <button className="text-left text-sm font-semibold text-[var(--brand)]" type="submit">Save overall judgment</button>
                        </form>
                        <form action={submitAssessment.bind(null, reviewId, assessment.id)}>
                          <button className={button} type="submit">Submit immutable assessment</button>
                        </form>
                      </div>
                    ) : null}
                  </article>
                );
              })}
            </div>
          </section>

          <section className="border-t border-[var(--line)] py-9">
            <h2 className="text-2xl font-semibold">AI proposals and evaluation</h2>
            <p className="mt-2 text-sm text-[var(--muted)]">Proposal visibility follows the selected mode. Evidence references remain tied to the pinned parser snapshot; stale proposals must not be accepted.</p>
            <div className="mt-6 space-y-5">
              {aiResult.proposals.map((proposal) => (
                <article className="rounded-2xl border border-[var(--line)] bg-white p-6" key={proposal.proposal_id ?? proposal.ai_run_id}>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h3 className="font-semibold">Assessment {proposal.assessment_id}</h3>
                      <p className="mt-1 text-xs text-[var(--muted)]">{proposal.mode} · {proposal.status} · {proposal.is_revealed ? "revealed" : "blinded"}{proposal.stale ? " · stale" : ""}</p>
                    </div>
                    <span className="rounded-full bg-[#edf4f0] px-3 py-1 text-xs font-semibold">{proposal.readiness}</span>
                  </div>
                  {proposal.stale_reasons.length ? <p className="mt-3 text-sm text-red-700">Staleness: {proposal.stale_reasons.join(", ")}</p> : null}
                  {proposal.is_revealed && proposal.structured_value ? (
                    <div className="mt-5 space-y-4">
                      {proposal.structured_value.answers?.map((answer) => (
                        <div className="rounded-xl border border-[var(--line)] p-4" key={answer.question_key}>
                          <div className="flex flex-wrap justify-between gap-2 text-sm">
                            <span className="font-semibold">{answer.question_key}</span>
                            <span>{answer.status} · {answer.answer ?? "abstained"}</span>
                          </div>
                          {answer.evidence.map((evidence) => <blockquote className="mt-3 border-l-4 border-[var(--brand)] bg-slate-50 p-3 text-sm" key={`${evidence.chunk_id}-${evidence.quote}`}><p className="text-xs text-[var(--muted)]">Document {evidence.document_id} · {evidence.section ?? "section unavailable"}</p><p className="mt-1">“{evidence.quote}”</p></blockquote>)}
                          {proposal.proposal_id ? (
                            <form action={reviewAIRiskOfBiasAnswer.bind(null, reviewId, proposal.proposal_id, answer.question_key)} className="mt-4 grid gap-3 sm:grid-cols-[10rem_1fr_auto] sm:items-end">
                              <label className="text-xs font-semibold">Disposition<select className={field} defaultValue="UNRESOLVED" name="action"><option value="ACCEPTED">Accept</option><option value="EDITED">Edit</option><option value="REJECTED">Reject</option><option value="UNRESOLVED">Unresolved</option></select></label>
                              <label className="text-xs font-semibold">Rationale / edited answer<input className={field} name="reason" /></label>
                              <button className="text-sm font-semibold text-[var(--brand)]" type="submit">Record disposition</button>
                            </form>
                          ) : null}
                        </div>
                      ))}
                      <div className="rounded-xl bg-[#edf4f0] p-4 text-sm"><p className="font-semibold">Deterministic rule output</p><p className="mt-1">Domain suggestions remain provisional: {JSON.stringify(proposal.domain_suggestions)}</p><p>Overall suggestion: {proposal.overall_suggestion ?? "not available"}</p></div>
                    </div>
                  ) : <p className="mt-4 rounded-xl bg-slate-50 p-4 text-sm text-[var(--muted)]">AI content is withheld until the governed reveal condition is met.</p>}
                </article>
              ))}
              {aiResult.proposals.length === 0 ? <p className="rounded-xl border border-dashed border-[var(--line)] p-5 text-sm text-[var(--muted)]">No governed AI proposals have been created.</p> : null}
            </div>
            {aiResult.evaluations.length ? <pre className="mt-6 overflow-auto rounded-xl bg-slate-950 p-4 text-xs text-slate-100">{JSON.stringify(aiResult.evaluations[0].metrics, null, 2)}</pre> : null}
          </section>

          <section className="grid gap-6 border-t border-[var(--line)] py-9 lg:grid-cols-2">
            <form action={compareAssessments.bind(null, reviewId)} className="rounded-2xl border border-[var(--line)] bg-white p-6">
              <h2 className="text-xl font-semibold">Compare submitted assessments</h2>
              {(["assessment_a_id", "assessment_b_id"] as const).map((name, index) => (
                <label className="mt-4 block text-sm font-semibold" key={name}>Assessment {index + 1}
                  <select className={field} name={name} required>
                    <option value="">Select</option>
                    {submitted.map((assessment) => <option key={assessment.id} value={assessment.id}>{studyById[assessment.study_id]?.study_key ?? assessment.study_id} &middot; assessor {assessment.assessor_user_id.slice(0, 8)}</option>)}
                  </select>
                </label>
              ))}
              <button className={`${button} mt-5`} type="submit">Detect agreement or conflict</button>
            </form>
            <div className="space-y-4">
              {result.comparisons.map((comparison) => (
                <article className="rounded-2xl border border-[var(--line)] bg-white p-6" key={comparison.id}>
                  <h3 className="font-semibold">{studyById[comparison.study_id]?.study_key ?? comparison.study_id} &middot; {comparison.status}</h3>
                  <ul className="mt-3 space-y-1 text-sm text-[var(--muted)]">
                    {comparison.differences.map((difference) => <li key={`${difference.scope}-${difference.key}`}>{difference.scope}: {difference.key} ({String(difference.value_a)} / {String(difference.value_b)})</li>)}
                  </ul>
                  {comparison.status === "CONFLICT" ? (
                    <form action={adjudicateComparison.bind(null, reviewId, comparison.id)} className="mt-4 space-y-3">
                      <select className={field} name="resolution_assessment_id" required>
                        <option value={comparison.assessment_a_id}>Accept assessment A</option>
                        <option value={comparison.assessment_b_id}>Accept assessment B</option>
                      </select>
                      <textarea className={field} name="rationale" placeholder="Adjudication rationale" required />
                      <input className={field} name="evidence_location_id" placeholder="Evidence location ID (optional)" />
                      <button className={button} type="submit">Adjudicate</button>
                    </form>
                  ) : null}
                </article>
              ))}
            </div>
          </section>
        </>
      )}
    </main>
  );
}

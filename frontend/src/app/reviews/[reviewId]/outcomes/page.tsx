import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { getOutcomeWorkspace } from "@/lib/api";
import { getAIOutcomeWorkspace } from "@/lib/ai-outcomes-api";

import {
  createCandidate,
  createAIOutcomePolicy,
  createMapping,
  createOutcome,
  createScale,
  createTimepointWindow,
  createUnit,
  deriveEffect,
  evaluateCandidate,
  generateAIOutcomeProposal,
  reviewAIOutcomeProposal,
} from "./actions";

type Props = {
  params: Promise<{ reviewId: string }>;
  searchParams: Promise<{ error?: string; updated?: string }>;
};

const field = "mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-sm";
const button = "rounded-full bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white";

export default async function OutcomesPage({ params, searchParams }: Props) {
  const [{ reviewId }, query, cookieStore] = await Promise.all([params, searchParams, cookies()]);
  const accessToken = cookieStore.get("review_access_token")?.value;
  const organizationId = cookieStore.get("review_organization_id")?.value;
  if (!accessToken || !organizationId) redirect("/login");
  const [result, aiResult] = await Promise.all([
    getOutcomeWorkspace(accessToken, organizationId, reviewId),
    getAIOutcomeWorkspace(accessToken, organizationId, reviewId),
  ]);
  if (result.status === "unauthorized") redirect("/login?error=session_expired");
  const versions = result.outcomes.flatMap((outcome) => outcome.versions);
  const versionById = Object.fromEntries(versions.map((version) => [version.id, version]));
  const studyById = Object.fromEntries(result.studies.map((study) => [study.id, study]));
  const latestReadiness = Object.fromEntries(
    result.readiness.map((snapshot) => [snapshot.candidate_set_id, snapshot]),
  );

  return (
    <main className="mx-auto min-h-screen w-full max-w-7xl px-6 py-8 sm:px-10 lg:px-14">
      <header className="border-b border-[var(--line)] pb-7">
        <Link className="text-sm font-semibold text-[var(--brand)] hover:underline" href="/reviews">
          &larr; Review projects
        </Link>
        <p className="mt-6 text-xs font-bold uppercase tracking-[0.22em] text-[var(--brand)]">
          Synthesis preparation
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-[-0.03em]">
          Outcomes &amp; effect estimates
        </h1>
        <p className="mt-2 max-w-3xl text-sm text-[var(--muted)]">
          Map verified extraction values to versioned outcomes, preserve timing and units, derive
          foundational estimates, and inspect deterministic readiness before any pooling.
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
          <h2 className="mt-2 text-2xl font-semibold">Outcome harmonization assistant</h2>
          <p className="mt-2 text-sm text-[var(--muted)]">
            The assistant proposes only evidence-grounded mappings or reported effect candidates.
            It cannot convert values, calculate effects, pool studies, or write a canonical record.
            A human must review the proposal and provide the explicit canonical payload.
          </p>
          <form action={createAIOutcomePolicy.bind(null, reviewId)} className="mt-5 space-y-3 rounded-xl bg-[#edf4f0] p-4">
            <label className="block text-xs font-semibold">Maximum proposal batch size
              <input className={field} defaultValue="20" min="1" max="100" name="maximum_batch_size" type="number" />
            </label>
            <button className={button} type="submit">Save governed policy</button>
          </form>
        </div>
        <div>
          <form action={generateAIOutcomeProposal.bind(null, reviewId)} className="rounded-xl border border-[var(--line)] bg-white p-5">
            <h3 className="font-semibold">Prepare a document-grounded proposal</h3>
            <p className="mt-1 text-xs text-[var(--muted)]">Only verified extraction values and processed Documents linked to the Study are eligible. The first Document is the primary full text.</p>
            <label className="mt-4 block text-xs font-semibold">Verified extraction value UUID
              <input className={field} name="extraction_value_id" placeholder="Extraction value UUID" required />
            </label>
            <label className="mt-4 block text-xs font-semibold">Outcome version
              <select className={field} name="outcome_version_id" required>
                <option value="">Select outcome version</option>
                {versions.map((version) => <option key={version.id} value={version.id}>{version.definition.name} v{version.version}</option>)}
              </select>
            </label>
            <label className="mt-4 block text-xs font-semibold">Processed Document UUIDs
              <textarea className={field} name="document_ids" placeholder="Document UUIDs separated by spaces or commas" required />
            </label>
            <button className={`${button} mt-4`} type="submit">Generate proposal</button>
          </form>
          {aiResult.status === "unauthorized" ? <p className="mt-3 text-sm text-[var(--muted)]">Outcome assistance is restricted to authorized review roles.</p> : null}
          {aiResult.status === "unavailable" ? <p className="mt-3 text-sm text-amber-800">Outcome assistance is temporarily unavailable; canonical outcome records are unaffected.</p> : null}
        </div>
      </section>

      {aiResult.status === "ready" && aiResult.proposals.length > 0 ? (
        <section className="border-b border-[var(--line)] py-8">
          <h2 className="text-2xl font-semibold">AI proposals awaiting human disposition</h2>
          <div className="mt-5 space-y-5">
            {aiResult.proposals.map((proposal) => (
              <article className="rounded-2xl border border-[var(--line)] bg-white p-5" key={proposal.proposal_id ?? `${proposal.extraction_value_id}-${proposal.outcome_version_id}`}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="font-semibold">{String(proposal.structured_value?.candidate_type ?? proposal.status)}</h3>
                    <p className="mt-1 break-all font-mono text-xs text-[var(--muted)]">Extraction {proposal.extraction_value_id} &middot; outcome {proposal.outcome_version_id}</p>
                  </div>
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold ${proposal.stale ? "bg-amber-100 text-amber-900" : "bg-[#edf4f0]"}`}>
                    {proposal.stale ? "STALE" : proposal.validation_results?.aggregate_valid ? "VALIDATED" : "REVIEW REQUIRED"}
                  </span>
                </div>
                <p className="mt-3 text-sm text-[var(--muted)]">{String(proposal.structured_value?.rationale ?? proposal.failure_reason ?? "No rationale returned.")}</p>
                <details className="mt-4 rounded-xl bg-[#f7f8f6] p-3">
                  <summary className="cursor-pointer text-xs font-semibold">Inspect pinned proposal and evidence</summary>
                  <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap break-words text-[11px]">{JSON.stringify({ structured_value: proposal.structured_value, validation_results: proposal.validation_results, source_manifest: proposal.source_manifest, selected_chunk_ids: proposal.selected_chunk_ids }, null, 2)}</pre>
                </details>
                {proposal.proposal_id ? (
                  <form action={reviewAIOutcomeProposal.bind(null, reviewId, proposal.proposal_id)} className="mt-5 grid gap-3 border-t border-[var(--line)] pt-4 lg:grid-cols-4">
                    <label className="text-xs font-semibold">Human disposition
                      <select className={field} name="action"><option>REJECTED</option><option>UNRESOLVED</option><option>ACCEPTED</option><option>EDITED</option></select>
                    </label>
                    <label className="text-xs font-semibold">Canonical action
                      <select className={field} name="canonical_action"><option value="">No canonical write</option><option>CREATE_MAPPING</option><option>CREATE_EFFECT_ESTIMATE</option></select>
                    </label>
                    <label className="text-xs font-semibold lg:col-span-2">Human canonical payload (JSON)
                      <textarea className={`${field} font-mono text-[11px]`} name="human_payload" placeholder='{"rationale":"..."}' />
                    </label>
                    <label className="text-xs font-semibold lg:col-span-3">Reason
                      <input className={field} name="reason" />
                    </label>
                    <button className={`${button} self-end`} type="submit">Record disposition</button>
                  </form>
                ) : null}
              </article>
            ))}
          </div>
        </section>
      ) : null}

      {result.status === "unavailable" ? (
        <section className="mt-8 rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-900">
          The outcome service is unavailable. No scientific record was changed.
        </section>
      ) : (
        <>
          <section className="grid gap-6 py-9 lg:grid-cols-2 xl:grid-cols-4">
            <form action={createTimepointWindow.bind(null, reviewId)} className="rounded-2xl border border-[var(--line)] bg-white p-6">
              <h2 className="text-lg font-semibold">Canonical timepoint window</h2>
              <label className="mt-4 block text-xs font-semibold">Key<input className={field} name="key" placeholder="FOUR_WEEKS" required /></label>
              <label className="mt-3 block text-xs font-semibold">Label<input className={field} name="label" placeholder="4 weeks +/- 7 days" required /></label>
              <label className="mt-3 block text-xs font-semibold">Anchor<select className={field} name="anchor"><option>INTERVENTION_START</option><option>RANDOMIZATION</option><option>BASELINE</option><option>DIAGNOSIS</option><option>OTHER</option></select></label>
              <div className="mt-3 grid grid-cols-2 gap-3">
                <label className="text-xs font-semibold">Minimum days<input className={field} name="minimum_days" type="number" step="any" /></label>
                <label className="text-xs font-semibold">Maximum days<input className={field} name="maximum_days" type="number" step="any" /></label>
              </div>
              <input name="rule_version" type="hidden" value="1" />
              <button className={`${button} mt-4`} type="submit">Create immutable window</button>
            </form>

            <form action={createUnit.bind(null, reviewId)} className="rounded-2xl border border-[var(--line)] bg-white p-6">
              <h2 className="text-lg font-semibold">Structured unit</h2>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <label className="text-xs font-semibold">Key<input className={field} name="key" placeholder="G" required /></label>
                <label className="text-xs font-semibold">Label<input className={field} name="label" placeholder="g" required /></label>
                <label className="text-xs font-semibold">Dimension<input className={field} name="dimension" placeholder="MASS" required /></label>
                <label className="text-xs font-semibold">Context<input className={field} defaultValue="GENERAL" name="context_key" required /></label>
                <label className="text-xs font-semibold">Base unit key<input className={field} name="base_unit_key" required /></label>
                <label className="text-xs font-semibold">Multiplier to base<input className={field} defaultValue="1" name="multiplier_to_base" type="number" step="any" /></label>
              </div>
              <input name="offset_to_base" type="hidden" value="0" /><input name="precision" type="hidden" value="6" /><input name="rule_version" type="hidden" value="1" />
              <button className={`${button} mt-4`} type="submit">Create immutable unit</button>
            </form>

            <form action={createOutcome.bind(null, reviewId)} className="rounded-2xl border border-[var(--line)] bg-white p-6">
              <h2 className="text-lg font-semibold">Canonical outcome v1</h2>
              <label className="mt-4 block text-xs font-semibold">Key<input className={field} name="key" placeholder="ALL_CAUSE_MORTALITY" required /></label>
              <label className="mt-3 block text-xs font-semibold">Name<input className={field} name="name" required /></label>
              <label className="mt-3 block text-xs font-semibold">Description<textarea className={field} name="description" /></label>
              <div className="mt-3 grid grid-cols-2 gap-3">
                <label className="text-xs font-semibold">Type<select className={field} name="outcome_type"><option>DICHOTOMOUS</option><option>CONTINUOUS</option><option>TIME_TO_EVENT</option><option>COUNT</option><option>PROPORTION</option><option>RATE</option><option>ORDINAL</option></select></label>
                <label className="text-xs font-semibold">Direction<select className={field} name="directionality"><option>HIGHER_WORSE</option><option>HIGHER_BETTER</option><option>NEUTRAL</option><option>UNKNOWN</option></select></label>
                <label className="text-xs font-semibold">Role<select className={field} name="role"><option>PRIMARY</option><option>SECONDARY</option><option>OTHER</option></select></label>
                <label className="text-xs font-semibold">Effect measures<input className={field} defaultValue="RR,OR,RD" name="compatible_effect_measures" /></label>
              </div>
              <label className="mt-3 block text-xs font-semibold">Expected window<select className={field} name="timepoint_window_id"><option value="">No fixed window</option>{result.configuration.timepoint_windows.map((window) => <option key={window.id} value={window.id}>{window.label}</option>)}</select></label>
              <button className={`${button} mt-4`} type="submit">Create outcome and version</button>
            </form>

            <form action={createScale.bind(null, reviewId)} className="rounded-2xl border border-[var(--line)] bg-white p-6">
              <h2 className="text-lg font-semibold">Measurement scale</h2>
              <label className="mt-4 block text-xs font-semibold">Key<input className={field} name="key" placeholder="PHQ_9" required /></label>
              <label className="mt-3 block text-xs font-semibold">Name<input className={field} name="name" placeholder="PHQ-9" required /></label>
              <div className="mt-3 grid grid-cols-2 gap-3"><label className="text-xs font-semibold">Minimum<input className={field} name="minimum" type="number" step="any" /></label><label className="text-xs font-semibold">Maximum<input className={field} name="maximum" type="number" step="any" /></label></div>
              <label className="mt-3 block text-xs font-semibold">Direction<select className={field} name="directionality"><option>HIGHER_WORSE</option><option>HIGHER_BETTER</option><option>UNKNOWN</option><option>NEUTRAL</option></select></label>
              <button className={`${button} mt-4`} type="submit">Create immutable scale</button>
            </form>
          </section>

          <section className="grid gap-6 border-t border-[var(--line)] py-9 lg:grid-cols-2">
            <form action={createMapping.bind(null, reviewId)} className="rounded-2xl border border-[var(--line)] bg-white p-6">
              <h2 className="text-xl font-semibold">Map verified extraction</h2>
              <p className="mt-2 text-sm text-[var(--muted)]">Labels are never auto-mapped. Record the exact extraction value ID and rationale.</p>
              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                <label className="text-xs font-semibold">Study<select className={field} name="study_id" required><option value="">Select Study</option>{result.studies.map((study) => <option key={study.id} value={study.id}>{study.study_key}</option>)}</select></label>
                <label className="text-xs font-semibold">Outcome version<select className={field} name="outcome_version_id" required><option value="">Select outcome</option>{versions.map((version) => <option key={version.id} value={version.id}>{version.definition.name} v{version.version}</option>)}</select></label>
                <label className="text-xs font-semibold">Extraction value ID<input className={field} name="extraction_value_id" required /></label>
                <label className="text-xs font-semibold">Canonical window<select className={field} name="timepoint_window_id"><option value="">Unmapped</option>{result.configuration.timepoint_windows.map((window) => <option key={window.id} value={window.id}>{window.label}</option>)}</select></label>
                <label className="text-xs font-semibold">Reported time<input className={field} name="reported_time_value" type="number" step="any" /></label>
                <label className="text-xs font-semibold">Reported time unit<select className={field} name="reported_time_unit"><option value="">Not recorded</option><option>DAY</option><option>WEEK</option><option>MONTH</option><option>YEAR</option></select></label>
                <label className="text-xs font-semibold">Reported anchor<select className={field} name="reported_time_anchor"><option value="">Not recorded</option><option>INTERVENTION_START</option><option>RANDOMIZATION</option><option>BASELINE</option><option>DIAGNOSIS</option><option>OTHER</option></select></label>
                <label className="text-xs font-semibold">Reported unit<select className={field} name="reported_unit_id"><option value="">Unstructured/original only</option>{result.configuration.units.map((unit) => <option key={unit.id} value={unit.id}>{unit.label} ({unit.context_key})</option>)}</select></label>
                <label className="text-xs font-semibold">Normalized unit<select className={field} name="normalized_unit_id"><option value="">No conversion</option>{result.configuration.units.map((unit) => <option key={unit.id} value={unit.id}>{unit.label} ({unit.context_key})</option>)}</select></label>
                <label className="text-xs font-semibold">Direction transform<select className={field} name="direction_transformation"><option>NONE</option><option>SIGN_REVERSED</option></select></label>
                <label className="text-xs font-semibold">Transformation reason<input className={field} name="transformation_reason" /></label>
                <label className="text-xs font-semibold sm:col-span-2">Mapping rationale<textarea className={field} name="rationale" required /></label>
              </div>
              <button className={`${button} mt-5`} type="submit">Record immutable mapping</button>
            </form>

            <form action={deriveEffect.bind(null, reviewId)} className="rounded-2xl border border-[var(--line)] bg-white p-6">
              <h2 className="text-xl font-semibold">Derive foundational effect</h2>
              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                <label className="text-xs font-semibold">Source mapping<select className={field} name="source_mapping_id" required><option value="">Select mapping</option>{result.mappings.map((mapping) => <option key={mapping.id} value={mapping.id}>{studyById[mapping.study_id]?.study_key ?? mapping.study_id} &middot; {versionById[mapping.outcome_version_id]?.definition.name}</option>)}</select></label>
                <label className="text-xs font-semibold">Study<select className={field} name="study_id" required>{result.studies.map((study) => <option key={study.id} value={study.id}>{study.study_key}</option>)}</select></label>
                <label className="text-xs font-semibold">Outcome version<select className={field} name="outcome_version_id" required>{versions.map((version) => <option key={version.id} value={version.id}>{version.definition.name} v{version.version}</option>)}</select></label>
                <label className="text-xs font-semibold">Effect measure<select className={field} name="effect_measure"><option>RR</option><option>OR</option><option>RD</option><option>MD</option></select></label>
                <label className="text-xs font-semibold">Window<select className={field} name="timepoint_window_id"><option value="">Unmapped</option>{result.configuration.timepoint_windows.map((window) => <option key={window.id} value={window.id}>{window.label}</option>)}</select></label>
                <label className="text-xs font-semibold">Analysis population<select className={field} name="analysis_population"><option>INTENTION_TO_TREAT</option><option>PER_PROTOCOL</option><option>MODIFIED_ITT</option><option>SAFETY</option><option>UNCLEAR</option></select></label>
              </div>
              <input name="adjustment" type="hidden" value="UNADJUSTED" />
              <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
                {[["events_intervention", "Events I"], ["sample_intervention", "N I"], ["events_comparator", "Events C"], ["sample_comparator", "N C"], ["mean_intervention", "Mean I"], ["sd_intervention", "SD I"], ["mean_comparator", "Mean C"], ["sd_comparator", "SD C"]].map(([name, label]) => <label className="text-xs font-semibold" key={name}>{label}<input className={field} name={name} type="number" step="any" /></label>)}
              </div>
              <button className={`${button} mt-5`} type="submit">Derive with deterministic formula</button>
            </form>
          </section>

          <section className="border-t border-[var(--line)] py-9">
            <h2 className="text-2xl font-semibold">Harmonized records</h2>
            <div className="mt-6 grid gap-5 lg:grid-cols-2">
              {result.estimates.map((estimate) => (
                <article className="rounded-2xl border border-[var(--line)] bg-white p-5" key={estimate.id}>
                  <div className="flex items-start justify-between gap-3"><div><h3 className="font-semibold">{versionById[estimate.outcome_version_id]?.definition.name ?? estimate.outcome_version_id}</h3><p className="mt-1 text-xs text-[var(--muted)]">{studyById[estimate.study_id]?.study_key} &middot; {estimate.effect_measure} &middot; {estimate.origin}</p></div><span className="rounded-full bg-[#edf4f0] px-3 py-1 font-mono text-sm">{estimate.estimate ?? "policy required"}</span></div>
                  <dl className="mt-4 grid grid-cols-2 gap-2 text-xs"><div><dt className="text-[var(--muted)]">Variance</dt><dd>{estimate.variance ?? "missing"} ({estimate.variance_scale})</dd></div><div><dt className="text-[var(--muted)]">Population</dt><dd>{estimate.analysis_population}</dd></div><div><dt className="text-[var(--muted)]">Calculation</dt><dd>{estimate.calculation_version ?? "reported"}</dd></div><div><dt className="text-[var(--muted)]">Zero events</dt><dd>{estimate.zero_event_pattern}</dd></div></dl>
                  <p className="mt-3 break-all font-mono text-[11px] text-[var(--muted)]">{estimate.id}</p>
                </article>
              ))}
            </div>
          </section>

          <section className="grid gap-6 border-t border-[var(--line)] py-9 lg:grid-cols-2">
            <form action={createCandidate.bind(null, reviewId)} className="rounded-2xl border border-[var(--line)] bg-white p-6">
              <h2 className="text-xl font-semibold">Candidate synthesis set</h2>
              <p className="mt-2 text-sm text-[var(--muted)]">Enter one or more estimate IDs separated by commas. No pooling is performed.</p>
              <label className="mt-4 block text-xs font-semibold">Outcome version<select className={field} name="outcome_version_id" required>{versions.map((version) => <option key={version.id} value={version.id}>{version.definition.name} v{version.version}</option>)}</select></label>
              <label className="mt-3 block text-xs font-semibold">Effect measure<select className={field} name="effect_measure"><option>RR</option><option>OR</option><option>RD</option><option>MD</option><option>SMD</option><option>HR</option></select></label>
              <label className="mt-3 block text-xs font-semibold">Window<select className={field} name="timepoint_window_id"><option value="">Unmapped</option>{result.configuration.timepoint_windows.map((window) => <option key={window.id} value={window.id}>{window.label}</option>)}</select></label>
              <label className="mt-3 block text-xs font-semibold">Population label<input className={field} name="population_label" /></label>
              <label className="mt-3 block text-xs font-semibold">Estimate IDs<textarea className={field} name="estimate_ids" required /></label>
              <button className={`${button} mt-4`} type="submit">Create immutable candidate set</button>
            </form>
            <div className="space-y-4">
              {result.candidates.map((candidate) => {
                const readiness = latestReadiness[candidate.id];
                return <article className="rounded-2xl border border-[var(--line)] bg-white p-6" key={candidate.id}><div className="flex items-start justify-between gap-3"><div><h3 className="font-semibold">{versionById[candidate.outcome_version_id]?.definition.name ?? candidate.outcome_version_id}</h3><p className="mt-1 text-xs text-[var(--muted)]">{candidate.effect_measure} &middot; {candidate.estimate_ids.length} estimate(s)</p></div><span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold">{readiness?.status ?? "NOT EVALUATED"}</span></div>{readiness?.blockers.length ? <ul className="mt-4 space-y-1 text-xs text-red-700">{readiness.blockers.map((blocker, index) => <li key={`${blocker.code}-${index}`}>{blocker.code}</li>)}</ul> : null}<form action={evaluateCandidate.bind(null, reviewId, candidate.id)} className="mt-4"><button className={button} type="submit">Evaluate readiness</button></form></article>;
              })}
            </div>
          </section>
        </>
      )}
    </main>
  );
}

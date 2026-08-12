import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";

import { type AnalysisArtifact, getAnalysisWorkspace, getOutcomeWorkspace } from "@/lib/api";

import {
  createAnalysisSet,
  createSpecification,
  executeAnalysis,
  generateForestPlot,
} from "./actions";

type Props = {
  params: Promise<{ reviewId: string }>;
  searchParams: Promise<{ error?: string; updated?: string }>;
};

const field = "mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-sm";
const button = "rounded-full bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white";

export default async function AnalysisPage({ params, searchParams }: Props) {
  const [{ reviewId }, query, cookieStore] = await Promise.all([params, searchParams, cookies()]);
  const accessToken = cookieStore.get("review_access_token")?.value;
  const organizationId = cookieStore.get("review_organization_id")?.value;
  if (!accessToken || !organizationId) redirect("/login");
  const [analysis, outcomes] = await Promise.all([
    getAnalysisWorkspace(accessToken, organizationId, reviewId),
    getOutcomeWorkspace(accessToken, organizationId, reviewId),
  ]);
  if (analysis.status === "unauthorized" || outcomes.status === "unauthorized") {
    redirect("/login?error=session_expired");
  }
  const unavailable = analysis.status === "unavailable" || outcomes.status === "unavailable";
  const outcomeVersions = outcomes.outcomes.flatMap((outcome) => outcome.versions);
  const outcomeById = Object.fromEntries(outcomeVersions.map((version) => [version.id, version]));
  const latestVersions = analysis.specifications.flatMap((item) => item.versions.slice(-1));
  const artifactsByRun = analysis.artifacts.reduce<Record<string, AnalysisArtifact[]>>(
    (grouped, artifact) => {
      (grouped[artifact.run_id] ??= []).push(artifact);
      return grouped;
    },
    {},
  );

  return (
    <main className="mx-auto min-h-screen w-full max-w-7xl px-6 py-8 sm:px-10 lg:px-14">
      <header className="border-b border-[var(--line)] pb-7">
        <Link className="text-sm font-semibold text-[var(--brand)] hover:underline" href="/reviews">
          &larr; Review projects
        </Link>
        <p className="mt-6 text-xs font-bold uppercase tracking-[0.22em] text-[var(--brand)]">
          Deterministic synthesis
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-[-0.03em]">Meta-analysis workspace</h1>
        <p className="mt-2 max-w-3xl text-sm text-[var(--muted)]">
          Persist every scientific choice, recheck harmonized inputs, and execute immutable
          inverse-variance analyses. Pooling never reads arbitrary extraction records.
        </p>
      </header>

      {query.error ? <p className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">The analysis operation was rejected ({query.error.replaceAll("_", " ")}).</p> : null}
      {query.updated ? <p className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">{query.updated.replaceAll("_", " ")}.</p> : null}

      {unavailable ? (
        <section className="mt-8 rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-900">
          The analysis workspace is unavailable. No scientific record was changed.
        </section>
      ) : (
        <>
          <section className="grid gap-6 py-9 lg:grid-cols-2">
            <form action={createSpecification.bind(null, reviewId)} className="rounded-2xl border border-[var(--line)] bg-white p-6">
              <h2 className="text-xl font-semibold">Versioned analysis specification</h2>
              <p className="mt-2 text-sm text-[var(--muted)]">Every consequential method and selection policy is explicit before execution.</p>
              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                <label className="text-xs font-semibold">Key<input className={field} name="key" placeholder="PRIMARY_MORTALITY" required /></label>
                <label className="text-xs font-semibold">Outcome version<select className={field} name="outcome_version_id" required><option value="">Select outcome</option>{outcomeVersions.map((version) => <option key={version.id} value={version.id}>{version.definition.name} v{version.version}</option>)}</select></label>
                <label className="text-xs font-semibold">Timepoint window<select className={field} name="timepoint_window_id"><option value="">No canonical window</option>{outcomes.configuration.timepoint_windows.map((window) => <option key={window.id} value={window.id}>{window.label}</option>)}</select></label>
                <label className="text-xs font-semibold">Synthesis population<input className={field} name="synthesis_population" required /></label>
                <label className="text-xs font-semibold">Intervention<input className={field} name="intervention" required /></label>
                <label className="text-xs font-semibold">Comparator<input className={field} name="comparator" required /></label>
                <label className="text-xs font-semibold">Eligible designs<input className={field} name="eligible_study_designs" placeholder="RANDOMIZED_CONTROLLED_TRIAL" required /></label>
                <label className="text-xs font-semibold">Effect measure<select className={field} name="effect_measure"><option>RR</option><option>OR</option><option>RD</option><option>MD</option><option>SMD</option><option>HR</option></select></label>
                <label className="text-xs font-semibold">Model<select className={field} name="model"><option>FIXED_EFFECT</option><option>RANDOM_EFFECTS</option></select></label>
                <label className="text-xs font-semibold">Confidence level<input className={field} defaultValue="0.95" name="confidence_level" type="number" min="0.5" max="0.999" step="0.001" /></label>
                <label className="text-xs font-semibold">Zero-event policy<select className={field} name="zero_event_policy"><option>BLOCK</option><option>EXCLUDE_DOUBLE_ZERO</option></select></label>
                <label className="text-xs font-semibold">Adjustment policy<select className={field} name="adjustment_policy"><option>UNADJUSTED_ONLY</option><option>ADJUSTED_ONLY</option><option>EITHER_EXPLICIT_SELECTION</option></select></label>
                <label className="text-xs font-semibold">Analysis population<select className={field} name="analysis_population"><option>INTENTION_TO_TREAT</option><option>PER_PROTOCOL</option><option>MODIFIED_ITT</option><option>SAFETY</option><option>UNCLEAR</option></select></label>
                <label className="text-xs font-semibold">Minimum Studies<input className={field} defaultValue="2" min="1" name="minimum_studies" type="number" /></label>
                <label className="text-xs font-semibold">SMD definition<select className={field} name="standardized_effect_definition"><option value="">Not SMD</option><option>HEDGES_G</option><option>COHEN_D</option></select></label>
                <label className="flex items-center gap-2 self-end pb-2 text-xs font-semibold"><input name="prediction_interval" type="checkbox" /> Request prediction interval</label>
              </div>
              <button className={`${button} mt-5`} type="submit">Persist specification v1</button>
            </form>

            <div className="space-y-6">
              <form action={createAnalysisSet.bind(null, reviewId)} className="rounded-2xl border border-[var(--line)] bg-white p-6">
                <h2 className="text-xl font-semibold">Materialize analysis set</h2>
                <p className="mt-2 text-sm text-[var(--muted)]">Select an already evaluated Phase 19 candidate and one estimate per Study.</p>
                <label className="mt-4 block text-xs font-semibold">Specification version<select className={field} name="specification_version_id" required><option value="">Select specification</option>{latestVersions.map((version) => <option key={version.id} value={version.id}>v{version.version} &middot; {outcomeById[version.definition.outcome_version_id]?.definition.name ?? version.id}</option>)}</select></label>
                <label className="mt-3 block text-xs font-semibold">Ready candidate<select className={field} name="candidate_set_id" required><option value="">Select candidate</option>{outcomes.candidates.map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.effect_measure} &middot; {candidate.estimate_ids.length} estimates</option>)}</select></label>
                <label className="mt-3 block text-xs font-semibold">Selected estimate IDs<textarea className={field} name="selected_estimate_ids" placeholder="Comma-separated immutable IDs" required /></label>
                <button className={`${button} mt-4`} type="submit">Revalidate and create set</button>
              </form>
              <aside className="rounded-2xl border border-blue-200 bg-blue-50 p-6 text-sm text-blue-950">
                <h2 className="font-semibold">Execution boundary</h2>
                <p className="mt-2">The persisted specification and immutable set—not transient form state—are sent to the deterministic engine. Duplicate Studies, stale inputs, unsupported dependencies, missing variance, and policy mismatches block execution.</p>
              </aside>
            </div>
          </section>

          <section className="border-t border-[var(--line)] py-9">
            <h2 className="text-2xl font-semibold">Analysis sets awaiting execution</h2>
            <div className="mt-6 grid gap-4 lg:grid-cols-2">
              {analysis.analysisSets.map((set) => (
                <article className="rounded-2xl border border-[var(--line)] bg-white p-5" key={set.id}>
                  <p className="text-sm font-semibold">{set.included_estimate_ids.length} independent Study estimate(s)</p>
                  <p className="mt-2 break-all font-mono text-[11px] text-[var(--muted)]">Input {set.input_hash}</p>
                  <form action={executeAnalysis.bind(null, reviewId, set.id)} className="mt-4"><button className={button} type="submit">Execute immutable run</button></form>
                </article>
              ))}
            </div>
          </section>

          <section className="border-t border-[var(--line)] py-9">
            <h2 className="text-2xl font-semibold">Completed runs</h2>
            <div className="mt-6 space-y-5">
              {analysis.runs.map((run) => (
                <article className="rounded-2xl border border-[var(--line)] bg-white p-6" key={run.id}>
                  <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold">{run.result?.model ?? "Analysis"} &middot; {run.status}</h3><p className="mt-1 text-xs text-[var(--muted)]">{run.algorithm_name} {run.algorithm_version} &middot; {run.provider}</p></div><span className={`rounded-full px-3 py-1 text-xs font-semibold ${run.stale ? "bg-amber-100 text-amber-900" : "bg-emerald-100 text-emerald-900"}`}>{run.stale ? "STALE" : "CURRENT"}</span></div>
                  {run.result ? <><p className="mt-5 text-2xl font-semibold">{run.result.presentation_estimate} <span className="text-sm font-normal text-[var(--muted)]">({run.result.presentation_ci_lower} to {run.result.presentation_ci_upper})</span></p><dl className="mt-4 grid gap-3 text-xs sm:grid-cols-5"><div><dt className="text-[var(--muted)]">Studies</dt><dd>{run.result.number_of_studies}</dd></div><div><dt className="text-[var(--muted)]">Estimator</dt><dd>{run.result.estimator}</dd></div><div><dt className="text-[var(--muted)]">Q (df)</dt><dd>{run.result.heterogeneity.q} ({run.result.heterogeneity.degrees_of_freedom})</dd></div><div><dt className="text-[var(--muted)]">I²</dt><dd>{run.result.heterogeneity.i_squared_percent}%</dd></div><div><dt className="text-[var(--muted)]">τ²</dt><dd>{run.result.heterogeneity.tau_squared}</dd></div></dl><p className="mt-4 text-xs text-[var(--muted)]">Leave-one-out results: {run.result.sensitivity.length}</p></> : <p className="mt-4 text-sm text-red-800">{run.failure_reason ?? "No canonical result was persisted."}</p>}
                  {run.diagnostics.length ? <ul className="mt-4 space-y-1 text-xs text-amber-900">{run.diagnostics.map((diagnostic, index) => <li key={`${diagnostic.code}-${index}`}>{diagnostic.level}: {diagnostic.code}</li>)}</ul> : null}
                  <div className="mt-5 flex flex-wrap gap-3"><form action={generateForestPlot.bind(null, reviewId, run.id)}><button className={button} disabled={run.status !== "COMPLETED"} type="submit">Generate forest plot</button></form>{(artifactsByRun[run.id] ?? []).map((artifact) => <a className="rounded-full border border-[var(--line)] px-4 py-2 text-sm font-semibold" href={`/api/reviews/${reviewId}/analysis-artifacts/${artifact.id}/download`} key={artifact.id}>Download {artifact.filename}</a>)}</div>
                  <p className="mt-4 break-all font-mono text-[11px] text-[var(--muted)]">Input {run.input_hash}{run.result_hash ? ` · Result ${run.result_hash}` : ""}</p>
                </article>
              ))}
            </div>
          </section>
        </>
      )}
    </main>
  );
}

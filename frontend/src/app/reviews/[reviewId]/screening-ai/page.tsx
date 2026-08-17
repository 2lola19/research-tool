import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";

import {
  getAIScreeningSuggestion,
  getAIScreeningWorkspace,
  type AIScreeningSuggestion,
} from "@/lib/ai-screening-api";

import {
  createAIScreeningEvaluationDataset,
  evaluateAIScreeningDataset,
  generateAIScreeningSuggestion,
  setAIScreeningPolicy,
} from "./actions";

type Props = {
  params: Promise<{ reviewId: string }>;
  searchParams: Promise<{
    round?: string;
    error?: string;
    updated?: string;
  }>;
};

const field = "mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-sm";
const button = "rounded-full bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white";

function metric(value: unknown): string {
  return typeof value === "number" ? `${(value * 100).toFixed(1)}%` : "n/a";
}

export default async function AIScreeningPage({ params, searchParams }: Props) {
  const [{ reviewId }, query, store] = await Promise.all([params, searchParams, cookies()]);
  const token = store.get("review_access_token")?.value;
  const organizationId = store.get("review_organization_id")?.value;
  if (!token || !organizationId) redirect("/login");

  const roundId = query.round;
  const workspace = await getAIScreeningWorkspace(token, organizationId, reviewId, roundId);
  if (workspace.status === "unauthorized") redirect("/login?error=session_expired");

  const suggestions = new Map<string, AIScreeningSuggestion>();
  if (roundId && workspace.queue.length > 0) {
    const loaded = await Promise.all(
      workspace.queue.map((item) =>
        getAIScreeningSuggestion(token, organizationId, reviewId, item.assignment_id),
      ),
    );
    loaded.forEach((suggestion, index) => {
      if (suggestion) suggestions.set(workspace.queue[index].assignment_id, suggestion);
    });
  }

  return (
    <main className="mx-auto min-h-screen w-full max-w-7xl px-6 py-8 sm:px-10 lg:px-14">
      <header className="border-b border-[var(--line)] pb-7">
        <Link className="text-sm font-semibold text-[var(--brand)] hover:underline" href="/reviews">
          &larr; Review projects
        </Link>
        <p className="mt-6 text-xs font-bold uppercase tracking-[0.22em] text-[var(--brand)]">
          Governed screening assistance
        </p>
        <h1 className="mt-2 text-3xl font-semibold">AI screening workspace</h1>
        <p className="mt-2 max-w-3xl text-sm text-[var(--muted)]">
          Suggestions are proposals only. Human screening decisions remain canonical, immutable,
          and independently auditable.
        </p>
        <Link
          className="mt-4 inline-block text-sm font-semibold text-[var(--brand)] hover:underline"
          href={`/reviews/${reviewId}/screening-ai/full-text`}
        >
          Open document-grounded full-text assistance &rarr;
        </Link>
      </header>

      {query.error ? (
        <p className="mt-6 rounded-xl bg-red-50 p-4 text-red-800" role="alert">
          The screening request was rejected safely.
        </p>
      ) : null}
      {query.updated ? (
        <p className="mt-6 rounded-xl bg-emerald-50 p-4 text-emerald-900" role="status">
          Screening workspace updated.
        </p>
      ) : null}

      <section className="grid gap-6 py-9 lg:grid-cols-[1fr_1.4fr]">
        <div className="rounded-2xl border border-[var(--line)] bg-white p-6">
          <h2 className="text-xl font-semibold">Assistance policy</h2>
          <p className="mt-2 text-sm text-[var(--muted)]">
            BLINDED_AI withholds suggestions until the reviewer records a decision. ASSISTED shows
            the proposal before the decision and records that access.
          </p>
          <form action={setAIScreeningPolicy.bind(null, reviewId)} className="mt-5">
            <label className="block text-xs font-semibold">
              Mode
              <select className={field} defaultValue={workspace.policy?.mode ?? "OFF"} name="mode">
                <option value="OFF">Off</option>
                <option value="BLINDED_AI">Blinded AI</option>
                <option value="ASSISTED">Assisted</option>
              </select>
            </label>
            <label className="mt-4 block text-xs font-semibold">
              Maximum batch size
              <input
                className={field}
                defaultValue={workspace.policy?.maximum_batch_size ?? 20}
                max={100}
                min={1}
                name="maximum_batch_size"
                type="number"
              />
            </label>
            <button className={`${button} mt-5`} type="submit">
              Save versioned policy
            </button>
          </form>
          {workspace.policy ? (
            <p className="mt-4 text-xs text-[var(--muted)]">
              Current version {workspace.policy.version} · {workspace.policy.mode}
            </p>
          ) : (
            <p className="mt-4 text-xs text-[var(--muted)]">No policy has been configured.</p>
          )}
        </div>

        <div className="rounded-2xl border border-[var(--line)] bg-white p-6">
          <h2 className="text-xl font-semibold">Reviewer queue</h2>
          <p className="mt-2 text-sm text-[var(--muted)]">
            Enter a title/abstract round identifier in the URL as <code>?round=...</code> to load
            your authorized queue.
          </p>
          {roundId ? (
            <div className="mt-5 space-y-4">
              {workspace.queue.length === 0 ? (
                <p className="rounded-xl bg-slate-50 p-4 text-sm">No assigned articles are available.</p>
              ) : (
                workspace.queue.map((item) => {
                  const suggestion = suggestions.get(item.assignment_id);
                  return (
                    <article className="rounded-xl border border-[var(--line)] p-4" key={item.assignment_id}>
                      <p className="font-semibold">{item.title}</p>
                      <p className="mt-2 text-sm text-[var(--muted)]">
                        {item.abstract ?? "No abstract supplied."}
                      </p>
                      <div className="mt-3 flex flex-wrap items-center gap-3 text-xs">
                        <span className="rounded-full bg-slate-100 px-3 py-1 font-semibold">
                          Human decision: {item.own_decision ?? "pending"}
                        </span>
                        {suggestion?.is_revealed ? (
                          <span className="rounded-full bg-emerald-50 px-3 py-1 font-semibold text-emerald-900">
                            AI: {suggestion.suggestion ?? "unavailable"}
                          </span>
                        ) : suggestion ? (
                          <span className="rounded-full bg-amber-50 px-3 py-1 font-semibold text-amber-900">
                            AI proposal withheld until decision
                          </span>
                        ) : null}
                      </div>
                      <form
                        action={generateAIScreeningSuggestion.bind(
                          null,
                          reviewId,
                           roundId,
                          item.assignment_id,
                        )}
                      >
                        <button className={`${button} mt-4`} type="submit">
                          Generate governed suggestion
                        </button>
                      </form>
                    </article>
                  );
                })
              )}
            </div>
          ) : null}
        </div>
      </section>

      <section className="grid gap-6 border-t border-[var(--line)] py-9 lg:grid-cols-2">
          <div>
            <h2 className="text-2xl font-semibold">Evaluation datasets</h2>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Curated reference standards remain separate from screening decisions and model output.
            </p>
            <form
              action={createAIScreeningEvaluationDataset.bind(null, reviewId)}
              className="mt-5 rounded-xl border border-[var(--line)] bg-white p-4"
            >
              <p className="text-sm font-semibold">Add a one-case reference fixture</p>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <input
                  className={field}
                  name="logical_key"
                  placeholder="Logical key"
                  required
                  type="text"
                />
                <input
                  className={field}
                  name="name"
                  placeholder="Dataset name"
                  required
                  type="text"
                />
                <input
                  className={field}
                  name="article_id"
                  placeholder="Article UUID"
                  required
                  type="text"
                />
                <select className={field} defaultValue="RETAIN" name="reference_decision">
                  <option value="RETAIN">Reference: retain</option>
                  <option value="EXCLUDE">Reference: exclude</option>
                </select>
              </div>
              <button className={`${button} mt-4`} type="submit">
                Save reference dataset
              </button>
            </form>
            <div className="mt-5 space-y-3">
            {workspace.datasets.length === 0 ? (
              <p className="rounded-xl border border-dashed border-[var(--line)] p-4 text-sm">
                No evaluation datasets yet.
              </p>
            ) : (
                workspace.datasets.map((dataset) => (
                  <article className="rounded-xl border border-[var(--line)] bg-white p-4" key={dataset.id}>
                    <p className="font-semibold">{dataset.name} v{dataset.version}</p>
                    <p className="mt-1 text-xs text-[var(--muted)]">
                      {dataset.reference_standard} · hash {dataset.content_hash.slice(0, 12)}…
                    </p>
                    <form action={evaluateAIScreeningDataset.bind(null, reviewId, dataset.id)}>
                      <button className={`${button} mt-3`} type="submit">
                        Run deterministic evaluation
                      </button>
                    </form>
                  </article>
                ))
            )}
          </div>
        </div>

        <div>
          <h2 className="text-2xl font-semibold">Deterministic evaluations</h2>
          <div className="mt-5 space-y-3">
            {workspace.evaluations.length === 0 ? (
              <p className="rounded-xl border border-dashed border-[var(--line)] p-4 text-sm">
                No evaluations yet.
              </p>
            ) : (
              workspace.evaluations.map((evaluation) => (
                <article className="rounded-xl border border-[var(--line)] bg-white p-4" key={evaluation.id}>
                  <p className="font-semibold">
                    {evaluation.evaluation_policy} · {evaluation.metric_version}
                  </p>
                  <dl className="mt-3 grid grid-cols-3 gap-2 text-xs">
                    <div><dt className="text-[var(--muted)]">Sensitivity</dt><dd className="font-semibold">{metric(evaluation.metrics.sensitivity)}</dd></div>
                    <div><dt className="text-[var(--muted)]">Specificity</dt><dd className="font-semibold">{metric(evaluation.metrics.specificity)}</dd></div>
                    <div><dt className="text-[var(--muted)]">Coverage</dt><dd className="font-semibold">{metric(evaluation.metrics.coverage)}</dd></div>
                  </dl>
                </article>
              ))
            )}
          </div>
        </div>
      </section>
    </main>
  );
}

import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { getSearchDocumentation } from "@/lib/api";

import {
  createIdentificationSource,
  createSearchExecution,
  linkSearchImport,
} from "./actions";

type SearchPageProps = {
  params: Promise<{ reviewId: string }>;
  searchParams: Promise<{ created?: string; error?: string }>;
};

const classifications = [
  "BIBLIOGRAPHIC_DATABASE",
  "TRIAL_REGISTER",
  "OTHER_REGISTER",
  "WEBSITE",
  "ORGANIZATION",
  "CITATION_SEARCHING",
  "REFERENCE_LIST",
  "AUTHOR_CONTACT",
  "MANUAL_IMPORT",
  "OTHER_SOURCE",
] as const;

const fieldClass =
  "mt-2 w-full rounded-xl border border-[var(--line)] bg-white px-3 py-2.5 text-sm";

export default async function SearchPage({ params, searchParams }: SearchPageProps) {
  const [{ reviewId }, query, cookieStore] = await Promise.all([params, searchParams, cookies()]);
  const accessToken = cookieStore.get("review_access_token")?.value;
  const organizationId = cookieStore.get("review_organization_id")?.value;
  if (!accessToken || !organizationId) redirect("/login");
  const result = await getSearchDocumentation(accessToken, organizationId, reviewId);
  if (result.status === "unauthorized") redirect("/login?error=session_expired");

  return (
    <main className="mx-auto min-h-screen w-full max-w-7xl px-6 py-8 sm:px-10 lg:px-14">
      <header className="border-b border-[var(--line)] pb-7">
        <Link className="text-sm font-semibold text-[var(--brand)] hover:underline" href="/reviews">
          &larr; Review projects
        </Link>
        <p className="mt-6 text-xs font-bold uppercase tracking-[0.22em] text-[var(--brand)]">
          Identification provenance
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-[-0.03em]">Search documentation</h1>
        <p className="mt-2 text-sm text-[var(--muted)]">
          Preserve what was actually searched, where, when, and how imported records arrived.
        </p>
      </header>

      {result.status === "unavailable" ? (
        <section className="mt-8 rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-900">
          The search documentation service is unavailable. No scientific record was changed.
        </section>
      ) : (
        <>
          {query.error ? (
            <p className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
              Search record update failed ({query.error.replaceAll("_", " ")}).
            </p>
          ) : null}
          {query.created ? (
            <p className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
              {query.created.replaceAll("_", " ")} provenance recorded.
            </p>
          ) : null}

          <section className="grid gap-6 py-9 lg:grid-cols-2">
            <form
              action={createIdentificationSource.bind(null, reviewId)}
              className="rounded-2xl border border-[var(--line)] bg-white p-6"
            >
              <h2 className="text-xl font-semibold">Add identification source</h2>
              <p className="mt-2 text-sm text-[var(--muted)]">
                Classification is structured and controls the PRISMA identification group.
              </p>
              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                <label className="text-sm font-semibold">
                  Source key
                  <input className={fieldClass} name="source_key" placeholder="pubmed" required />
                </label>
                <label className="text-sm font-semibold">
                  Display name
                  <input className={fieldClass} name="display_name" placeholder="PubMed" required />
                </label>
                <label className="text-sm font-semibold">
                  Classification
                  <select className={fieldClass} name="classification" required>
                    {classifications.map((classification) => (
                      <option key={classification} value={classification}>
                        {classification.replaceAll("_", " ")}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-sm font-semibold">
                  Provider
                  <input className={fieldClass} name="provider_name" placeholder="NCBI" required />
                </label>
                <label className="text-sm font-semibold sm:col-span-2">
                  Platform (optional)
                  <input className={fieldClass} name="platform_name" placeholder="PubMed web" />
                </label>
              </div>
              <button className="mt-5 rounded-full bg-[var(--brand)] px-5 py-2.5 text-sm font-semibold text-white" type="submit">
                Record source
              </button>
            </form>

            <form
              action={createSearchExecution.bind(null, reviewId)}
              className="rounded-2xl border border-[var(--line)] bg-white p-6"
            >
              <h2 className="text-xl font-semibold">Record search execution</h2>
              <p className="mt-2 text-sm text-[var(--muted)]">
                Completed executions are immutable. Corrections require a new execution.
              </p>
              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                <label className="text-sm font-semibold">
                  Source
                  <select className={fieldClass} name="source_id" required>
                    <option value="">Select a source</option>
                    {result.sources.map((source) => (
                      <option key={source.id} value={source.id}>
                        {source.display_name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-sm font-semibold">
                  Strategy version
                  <select className={fieldClass} name="search_strategy_version_id">
                    <option value="">External / not applicable</option>
                    {result.strategies.map((strategy) => (
                      <option key={strategy.id} value={strategy.id}>
                        {strategy.content.name} v{strategy.version}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="text-sm font-semibold">
                  Acquisition method
                  <select className={fieldClass} name="method" defaultValue="FILE_IMPORT">
                    {['API', 'FILE_IMPORT', 'MANUAL_RECORD', 'FIXTURE', 'MOCK', 'CONNECTOR'].map((method) => (
                      <option key={method} value={method}>{method.replaceAll('_', ' ')}</option>
                    ))}
                  </select>
                </label>
                <label className="text-sm font-semibold">
                  Status
                  <select className={fieldClass} name="status" defaultValue="COMPLETED">
                    {['PLANNED', 'RUNNING', 'COMPLETED', 'PARTIAL', 'FAILED', 'CANCELLED'].map((status) => (
                      <option key={status} value={status}>{status}</option>
                    ))}
                  </select>
                </label>
                <label className="text-sm font-semibold">
                  Execution date/time (UTC)
                  <input className={fieldClass} name="executed_at_utc" type="datetime-local" required />
                </label>
                <label className="text-sm font-semibold">
                  Provider result count
                  <input className={fieldClass} min="0" name="provider_result_count" type="number" />
                </label>
                <label className="text-sm font-semibold sm:col-span-2">
                  Exact executed query
                  <textarea className={`${fieldClass} min-h-28 font-mono`} name="exact_query" />
                </label>
                <label className="text-sm font-semibold">
                  Filters / restrictions
                  <input className={fieldClass} name="restrictions" placeholder="English; 2020-present" />
                </label>
                <label className="text-sm font-semibold">
                  Software / translator version
                  <input className={fieldClass} name="software_version" placeholder="translator/1" />
                </label>
                <label className="text-sm font-semibold sm:col-span-2">
                  Link citation import (optional)
                  <select className={fieldClass} name="import_batch_id">
                    <option value="">Link later</option>
                    {result.imports.map((batch) => (
                      <option key={batch.id} value={batch.id}>
                        {batch.source_name} ({batch.record_count} records)
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <button className="mt-5 rounded-full bg-[var(--brand)] px-5 py-2.5 text-sm font-semibold text-white" type="submit">
                Record execution
              </button>
            </form>
          </section>

          <section className="border-t border-[var(--line)] py-9" aria-labelledby="history-heading">
            <h2 id="history-heading" className="text-2xl font-semibold">Execution history</h2>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Ordered by execution date. Imported count is distinct from provider-reported results.
            </p>
            {result.executions.length === 0 ? (
              <p className="mt-6 rounded-2xl border border-dashed border-[var(--line)] bg-white p-8 text-center text-sm text-[var(--muted)]">
                No search execution has been recorded for this review.
              </p>
            ) : (
              <div className="mt-6 overflow-x-auto rounded-2xl border border-[var(--line)] bg-white">
                <table className="w-full min-w-[1000px] text-left text-sm">
                  <thead className="bg-[#edf4f0] text-xs uppercase tracking-wide text-[var(--muted)]">
                    <tr>
                      {['Source', 'Classification', 'Date', 'Method', 'Status', 'Returned', 'Imported', 'Query', 'Link import'].map((heading) => (
                        <th className="px-4 py-3" key={heading}>{heading}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--line)]">
                    {result.executions.map((execution) => (
                      <tr key={execution.id}>
                        <td className="px-4 py-4 font-semibold">{execution.source.display_name}</td>
                        <td className="px-4 py-4 text-xs">{execution.source.classification}</td>
                        <td className="px-4 py-4 whitespace-nowrap">{execution.executed_at}</td>
                        <td className="px-4 py-4">{execution.method}</td>
                        <td className="px-4 py-4">
                          <span className="font-semibold">{execution.status}</span>
                          <span className="mt-1 block text-xs text-[var(--muted)]">
                            {execution.events.map((event) => event.status).join(" → ")}
                          </span>
                        </td>
                        <td className="px-4 py-4">{execution.provider_result_count ?? '—'}</td>
                        <td className="px-4 py-4">{execution.imported_record_count}</td>
                        <td className="max-w-xs px-4 py-4 font-mono text-xs">{execution.exact_query ?? '—'}</td>
                        <td className="px-4 py-4">
                          {result.imports.length ? (
                            <form action={linkSearchImport.bind(null, reviewId, execution.id)} className="flex gap-2">
                              <select className="rounded-lg border border-[var(--line)] px-2 py-1" name="import_batch_id" required>
                                <option value="">Select</option>
                                {result.imports.map((batch) => <option key={batch.id} value={batch.id}>{batch.source_name}</option>)}
                              </select>
                              <button className="font-semibold text-[var(--brand)]" type="submit">Link</button>
                            </form>
                          ) : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}

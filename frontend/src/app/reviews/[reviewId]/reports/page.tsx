import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { getReviewReport } from "@/lib/api";

import { createExport } from "./actions";

type ReportsPageProps = {
  params: Promise<{ reviewId: string }>;
  searchParams: Promise<{ created?: string; error?: string }>;
};

const countLabels: Record<string, string> = {
  records_identified_databases: "Records identified",
  records_removed_duplicates: "Duplicates removed",
  records_screened: "Records screened",
  records_excluded_title_abstract: "Records excluded",
  reports_sought_for_retrieval: "Reports sought",
  reports_assessed_for_eligibility: "Reports assessed",
  studies_included_review: "Included studies",
  reports_of_included_studies: "Included reports",
};

function ReportsHeader({ reviewId }: { reviewId: string }) {
  return (
    <header className="border-b border-[var(--line)] pb-7">
      <Link className="text-sm font-semibold text-[var(--brand)] hover:underline" href="/reviews">
        &larr; Review projects
      </Link>
      <p className="mt-6 text-xs font-bold uppercase tracking-[0.22em] text-[var(--brand)]">
        Reproducible reporting
      </p>
      <h1 className="mt-2 text-3xl font-semibold tracking-[-0.03em]">Reports &amp; exports</h1>
      <p className="mt-2 font-mono text-xs text-[var(--muted)]">Review {reviewId}</p>
    </header>
  );
}

export default async function ReportsPage({ params, searchParams }: ReportsPageProps) {
  const [{ reviewId }, query, cookieStore] = await Promise.all([params, searchParams, cookies()]);
  const accessToken = cookieStore.get("review_access_token")?.value;
  const organizationId = cookieStore.get("review_organization_id")?.value;
  if (!accessToken || !organizationId) {
    redirect("/login");
  }
  const result = await getReviewReport(accessToken, organizationId, reviewId);
  if (result.status === "unauthorized") {
    redirect("/login?error=session_expired");
  }
  if (result.status === "unavailable") {
    return (
      <main className="mx-auto min-h-screen w-full max-w-7xl px-6 py-8 sm:px-10 lg:px-14">
        <ReportsHeader reviewId={reviewId} />
        <section className="mt-8 rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-900">
          The reporting service is unavailable. No export was created.
        </section>
      </main>
    );
  }

  return (
    <main className="mx-auto min-h-screen w-full max-w-7xl px-6 py-8 sm:px-10 lg:px-14">
      <ReportsHeader reviewId={reviewId} />
      <>
          {query.error ? (
            <p className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">
              Export creation failed ({query.error.replaceAll("_", " ")}).
            </p>
          ) : null}
          {query.created ? (
            <p className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-900">
              {query.created.toUpperCase()} artifact created with a reproducibility manifest.
            </p>
          ) : null}

          <section className="py-9" aria-labelledby="prisma-heading">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--brand)]">
                  Database-derived
                </p>
                <h2 id="prisma-heading" className="mt-2 text-2xl font-semibold">
                  PRISMA summary
                </h2>
              </div>
              <span
                className={`rounded-full px-4 py-2 text-sm font-semibold ${
                  result.summary.readiness.ready_for_final
                    ? "bg-emerald-100 text-emerald-900"
                    : "bg-amber-100 text-amber-900"
                }`}
              >
                {result.summary.readiness.ready_for_final ? "Ready for final" : "Draft only"}
              </span>
            </div>
            <dl className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {Object.entries(countLabels).map(([key, label]) => (
                <div className="rounded-2xl border border-[var(--line)] bg-white p-5" key={key}>
                  <dt className="text-sm text-[var(--muted)]">{label}</dt>
                  <dd className="mt-2 text-3xl font-semibold">{String(result.summary.counts[key] ?? 0)}</dd>
                </div>
              ))}
            </dl>
            {result.summary.readiness.blockers.length > 0 ? (
              <div className="mt-7 rounded-2xl border border-amber-200 bg-amber-50 p-6">
                <h3 className="font-semibold text-amber-950">Final-report blockers</h3>
                <ul className="mt-3 space-y-2 text-sm text-amber-900">
                  {result.summary.readiness.blockers.map((blocker) => (
                    <li key={blocker.code}>
                      <span className="font-mono font-semibold">{blocker.code}</span>: {blocker.message}
                      {blocker.count === null ? "" : ` (${blocker.count})`}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </section>

          <section className="border-t border-[var(--line)] py-9" aria-labelledby="exports-heading">
            <h2 id="exports-heading" className="text-2xl font-semibold">
              Immutable export artifacts
            </h2>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Each artifact captures a PRISMA snapshot, manifest, and SHA-256 checksum.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              {["CSV", "XLSX", "JSON", "RIS"].map((format) => (
                <form action={createExport.bind(null, reviewId)} key={format}>
                  <input name="format" type="hidden" value={format} />
                  <button
                    className="rounded-full bg-[var(--brand)] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[var(--brand-deep)]"
                    type="submit"
                  >
                    Create {format}
                  </button>
                </form>
              ))}
            </div>
            {result.exports.length === 0 ? (
              <p className="mt-7 rounded-2xl border border-dashed border-[var(--line)] bg-white p-8 text-center text-sm text-[var(--muted)]">
                No export artifacts have been created for this review.
              </p>
            ) : (
              <ul className="mt-7 divide-y divide-[var(--line)] rounded-2xl border border-[var(--line)] bg-white px-5">
                {result.exports.map((artifact) => (
                  <li className="grid gap-3 py-5 md:grid-cols-[1fr_auto] md:items-center" key={artifact.id}>
                    <div>
                      <p className="font-semibold">{artifact.filename}</p>
                      <p className="mt-1 break-all font-mono text-xs text-[var(--muted)]">
                        SHA-256 {artifact.sha256} &middot; {artifact.byte_size} bytes
                      </p>
                    </div>
                    <a
                      className="text-sm font-semibold text-[var(--brand)] hover:underline"
                      href={`/api/reviews/${reviewId}/exports/${artifact.id}/download`}
                    >
                      Download {artifact.format}
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </section>
      </>
    </main>
  );
}

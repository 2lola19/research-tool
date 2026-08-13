import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";

import { getReportingWorkspace } from "@/lib/api";

import { generateReport } from "./actions";

type Props = {
  params: Promise<{ reviewId: string }>;
  searchParams: Promise<{ error?: string; updated?: string }>;
};

const field = "mt-1 w-full rounded-lg border border-[var(--line)] bg-white px-3 py-2 text-sm";
const button = "rounded-full bg-[var(--brand)] px-4 py-2 text-sm font-semibold text-white";

export default async function ReportingPage({ params, searchParams }: Props) {
  const [{ reviewId }, query, cookieStore] = await Promise.all([params, searchParams, cookies()]);
  const token = cookieStore.get("review_access_token")?.value;
  const organizationId = cookieStore.get("review_organization_id")?.value;
  if (!token || !organizationId) redirect("/login");
  const workspace = await getReportingWorkspace(token, organizationId, reviewId);
  if (workspace.status === "unauthorized") redirect("/login?error=session_expired");

  return (
    <main className="mx-auto min-h-screen w-full max-w-7xl px-6 py-8 sm:px-10 lg:px-14">
      <header className="border-b border-[var(--line)] pb-7">
        <Link className="text-sm font-semibold text-[var(--brand)] hover:underline" href="/reviews">
          &larr; Review projects
        </Link>
        <p className="mt-6 text-xs font-bold uppercase tracking-[0.22em] text-[var(--brand)]">
          Deterministic scientific outputs
        </p>
        <h1 className="mt-2 text-3xl font-semibold">Reporting and reproducibility</h1>
        <p className="mt-2 max-w-3xl text-sm text-[var(--muted)]">
          Generate immutable structured artifacts from canonical review state. Reporting does not
          recalculate PRISMA, statistics, Risk of Bias, or certainty judgments.
        </p>
      </header>

      {query.error ? <p className="mt-6 rounded-xl bg-red-50 p-4 text-red-800">{query.error}</p> : null}
      {query.updated ? <p className="mt-6 rounded-xl bg-emerald-50 p-4 text-emerald-900">Report generated.</p> : null}

      <section className="grid gap-6 py-9 lg:grid-cols-2">
        <div className="rounded-2xl border border-[var(--line)] bg-white p-6">
          <h2 className="text-xl font-semibold">Package preview</h2>
          <p className="mt-3 text-sm text-[var(--muted)]">
            Included: protocol, searches, citations, screening, PRISMA, Studies, extraction, Risk of
            Bias, outcomes, analyses, certainty, and provenance metadata.
          </p>
          <p className="mt-3 text-sm font-semibold text-amber-800">
            Excluded: full-text binaries, raw provider bytes, secrets, environment files, and runtime
            artifacts.
          </p>
        </div>
        <form action={generateReport.bind(null, reviewId)} className="rounded-2xl border border-[var(--line)] bg-white p-6">
          <h2 className="text-xl font-semibold">Generate immutable snapshot</h2>
          <label className="mt-4 block text-xs font-semibold">
            Report type
            <select className={field} name="report_type">
              <option>STRUCTURED_REVIEW_REPORT</option>
              <option>EVIDENCE_PROFILE</option>
              <option>SUMMARY_OF_FINDINGS</option>
              <option>REPRODUCIBILITY_PACKAGE</option>
              <option>INTERNAL_REVIEW_REPORT</option>
            </select>
          </label>
          <label className="mt-4 block text-xs font-semibold">
            Formats for non-package reports
            <input className={field} defaultValue="JSON,HTML,XLSX" name="formats" />
          </label>
          <label className="mt-4 flex gap-2 text-sm">
            <input name="allow_draft" type="checkbox" /> Generate explicitly labelled draft when final readiness blocks
          </label>
          <button className={button + " mt-5"} type="submit">Generate</button>
        </form>
      </section>

      <section className="border-t border-[var(--line)] py-9">
        <h2 className="text-2xl font-semibold">Immutable artifacts</h2>
        <div className="mt-6 space-y-4">
          {workspace.snapshots.map((item) => (
            <article className="rounded-2xl border border-[var(--line)] bg-white p-6" key={item.snapshot.id}>
              <div className="flex flex-wrap justify-between gap-3">
                <div>
                  <h3 className="font-semibold">Snapshot {item.snapshot.id.slice(0, 8)}</h3>
                  <p className="mt-1 text-xs text-[var(--muted)]">Scientific hash {item.snapshot.scientific_content_hash}</p>
                </div>
                <span className={item.currency === "CURRENT" ? "text-emerald-700" : "text-amber-800"}>{item.currency}</span>
              </div>
              <div className="mt-4 flex flex-wrap gap-3">
                {item.artifacts.map((artifact) => (
                  <a className="text-sm font-semibold text-[var(--brand)] hover:underline" href={`/api/reviews/${reviewId}/report-artifacts/${artifact.id}/download`} key={artifact.id}>
                    Download {artifact.format} ({artifact.byte_size} bytes)
                  </a>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}


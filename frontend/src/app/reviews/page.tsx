import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";

import { getReviewProjects } from "@/lib/api";

export default async function ReviewsPage() {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get("review_access_token")?.value;
  const organizationId = cookieStore.get("review_organization_id")?.value;
  if (!accessToken || !organizationId) {
    redirect("/login");
  }

  const result = await getReviewProjects(accessToken, organizationId);
  if (result.status === "unauthorized") {
    redirect("/login?error=session_expired");
  }

  const activeProjects = result.projects.filter((project) => !project.archived);
  const archivedProjects = result.projects.filter((project) => project.archived);

  return (
    <main className="mx-auto min-h-screen w-full max-w-7xl px-6 py-8 sm:px-10 lg:px-14">
      <header className="flex flex-col gap-5 border-b border-[var(--line)] pb-7 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.22em] text-[var(--brand)]">
            Evidence workspace
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-[-0.03em]">Review projects</h1>
          <p className="mt-2 font-mono text-xs text-[var(--muted)]">
            Organization {organizationId}
          </p>
        </div>
        <form action="/api/session/logout" method="post">
          <button
            className="rounded-full border border-[var(--line)] bg-white px-5 py-2.5 text-sm font-semibold hover:border-[var(--brand)]"
            type="submit"
          >
            Sign out
          </button>
        </form>
      </header>

      {result.status === "unavailable" ? (
        <section
          className="mt-10 rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-900"
          role="status"
        >
          <h2 className="font-semibold">The project service is unavailable</h2>
          <p className="mt-2 text-sm">
            Your session is intact. Start the local API and refresh this page.
          </p>
        </section>
      ) : (
        <>
          <section className="py-10" aria-labelledby="active-projects-heading">
            <div className="flex items-end justify-between gap-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.18em] text-[var(--brand)]">
                  Current work
                </p>
                <h2 id="active-projects-heading" className="mt-2 text-2xl font-semibold">
                  Active projects
                </h2>
              </div>
              <span className="rounded-full bg-[#e7f1ec] px-3 py-1 text-sm font-semibold text-[var(--brand-deep)]">
                {activeProjects.length}
              </span>
            </div>

            {activeProjects.length === 0 ? (
              <div className="mt-7 rounded-2xl border border-dashed border-[var(--line)] bg-white p-10 text-center">
                <p className="font-semibold">No accessible review projects yet.</p>
                <p className="mt-2 text-sm text-[var(--muted)]">
                  Create one through the API or ask an organization owner to assign you.
                </p>
              </div>
            ) : (
              <div className="mt-7 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                {activeProjects.map((project) => (
                  <article
                    className="rounded-2xl border border-[var(--line)] bg-white p-6 shadow-[0_14px_45px_rgb(20_35_28/6%)]"
                    key={project.id}
                  >
                    <p className="font-mono text-xs text-[var(--brand)]">
                      {project.project_slug}
                    </p>
                    <h3 className="mt-4 text-xl font-semibold tracking-[-0.02em]">
                      {project.title}
                    </h3>
                    <p className="mt-3 min-h-12 text-sm leading-6 text-[var(--muted)]">
                      {project.description ?? "No project description has been added."}
                    </p>
                    <div className="mt-6 border-t border-[var(--line)] pt-4 text-xs text-[var(--muted)]">
                      Owner{" "}
                      <span className="font-mono text-[var(--foreground)]">
                        {project.owner_user_id.slice(0, 8)}
                      </span>
                    </div>
                    <div className="mt-5 flex gap-4 text-sm font-semibold text-[var(--brand)]">
                      <Link className="hover:underline" href={`/reviews/${project.id}/search`}>
                        Search
                      </Link>
                      <Link className="hover:underline" href={`/reviews/${project.id}/reports`}>
                        Reports &amp; exports
                      </Link>
                      <Link className="hover:underline" href={`/reviews/${project.id}/risk-of-bias`}>
                        Risk of Bias
                      </Link>
                      <Link className="hover:underline" href={`/reviews/${project.id}/outcomes`}>
                        Outcomes
                      </Link>
                      <Link className="hover:underline" href={`/reviews/${project.id}/analysis`}>
                        Analysis
                      </Link>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>

          {archivedProjects.length > 0 ? (
            <section
              className="border-t border-[var(--line)] py-10"
              aria-labelledby="archived-projects-heading"
            >
              <h2 id="archived-projects-heading" className="text-xl font-semibold">
                Archived projects
              </h2>
              <ul className="mt-5 divide-y divide-[var(--line)] rounded-2xl border border-[var(--line)] bg-white px-5">
                {archivedProjects.map((project) => (
                  <li className="flex items-center justify-between gap-4 py-4" key={project.id}>
                    <div>
                      <p className="font-semibold">{project.title}</p>
                      <p className="mt-1 font-mono text-xs text-[var(--muted)]">
                        {project.project_slug}
                      </p>
                    </div>
                    <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                      Archived
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </>
      )}
    </main>
  );
}

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import ReviewOperationsPanel from "@/components/review-operations-panel";
import { getReviewOperationsWorkspace } from "@/lib/review-workspace-api";

type Props = {
  params: Promise<{ reviewId: string }>;
  searchParams: Promise<{ round?: string; error?: string; updated?: string }>;
};

export default async function ReviewOverviewPage({ params, searchParams }: Props) {
  const [{ reviewId }, query, store] = await Promise.all([params, searchParams, cookies()]);
  const accessToken = store.get("review_access_token")?.value;
  const organizationId = store.get("review_organization_id")?.value;
  if (!accessToken || !organizationId) redirect("/login");

  const result = await getReviewOperationsWorkspace(
    accessToken,
    organizationId,
    reviewId,
    query.round,
  );
  if (result.status === "unauthorized") redirect("/login?error=session_expired");
  if (result.status === "unavailable") {
    return (
      <main className="mx-auto min-h-screen w-full max-w-7xl px-6 py-8 sm:px-10 lg:px-14">
        <section className="rounded-2xl border border-amber-200 bg-amber-50 p-6 text-amber-900" role="alert">
          <h1 className="text-2xl font-semibold">Review operations are unavailable</h1>
          <p className="mt-2 text-sm">The review could not be loaded safely. No scientific or workflow state was changed.</p>
        </section>
      </main>
    );
  }

  return <ReviewOperationsPanel reviewId={reviewId} query={query} workspace={result.workspace} />;
}

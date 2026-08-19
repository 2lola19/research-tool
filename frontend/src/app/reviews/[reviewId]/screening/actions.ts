"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

type ScreeningDecision = "INCLUDE" | "EXCLUDE";

async function post(path: string, body: Record<string, unknown>): Promise<Response | null> {
  const store = await cookies();
  const token = store.get("review_access_token")?.value;
  const organizationId = store.get("review_organization_id")?.value;
  if (!token || !organizationId) redirect("/login");
  try {
    return await fetch(`${process.env.API_BASE_URL ?? "http://localhost:8000"}${path}`, {
      method: "POST",
      cache: "no-store",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        "X-Organization-ID": organizationId,
      },
      body: JSON.stringify(body),
    });
  } catch {
    return null;
  }
}

function required(formData: FormData, name: string): string {
  return String(formData.get(name) ?? "").trim();
}

function redirectForResponse(reviewId: string, roundId: string, response: Response | null, action: string): never {
  if (!response) redirect(`/reviews/${reviewId}/screening?round=${roundId}&error=service_unavailable`);
  if (response.status === 401) redirect("/login?error=session_expired");
  if (response.status === 403) redirect(`/reviews/${reviewId}/screening?round=${roundId}&error=not_authorized`);
  if (!response.ok) redirect(`/reviews/${reviewId}/screening?round=${roundId}&error=${action}_rejected`);
  revalidatePath(`/reviews/${reviewId}`);
  redirect(`/reviews/${reviewId}/screening?round=${roundId}&updated=${action}`);
}

export async function assignScreeningArticle(reviewId: string, formData: FormData) {
  const roundId = required(formData, "round_id");
  const response = await post(`/api/v1/screening/rounds/${roundId}/assignments`, {
    article_id: required(formData, "article_id"),
    reviewer_user_id: required(formData, "reviewer_user_id"),
  });
  redirectForResponse(reviewId, roundId, response, "assignment");
}

export async function adjudicateScreeningOutcome(
  reviewId: string,
  outcomeId: string,
  roundId: string,
  decision: ScreeningDecision,
  formData: FormData,
) {
  const reason = required(formData, "reason");
  const response = await post(`/api/v1/screening/outcomes/${outcomeId}/adjudication`, {
    decision,
    reason,
  });
  redirectForResponse(reviewId, roundId, response, "adjudication");
}

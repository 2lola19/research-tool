"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

async function post(path: string, body: Record<string, unknown>) {
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

export async function createSearchSuggestion(reviewId: string, formData: FormData) {
  const response = await post("/api/v1/ai/runs", {
    review_id: reviewId,
    task_type: "SEARCH_QUERY_SUGGESTION",
    input_data: {
      query: String(formData.get("query") ?? ""),
      objective: String(formData.get("objective") ?? ""),
    },
  });
  if (!response?.ok) redirect(`/reviews/${reviewId}/ai?error=run_rejected`);
  const payload = (await response.json()) as { proposal: { id: string } | null };
  revalidatePath(`/reviews/${reviewId}/ai`);
  redirect(`/reviews/${reviewId}/ai?proposal=${payload.proposal?.id ?? ""}`);
}

export async function createCopilotPolicy(reviewId: string, formData: FormData) {
  const response = await post(`/api/v1/ai/copilot/reviews/${reviewId}/policies`, {
    maximum_query_characters: Number(formData.get("maximum_query_characters") ?? 2_000),
    maximum_context_items: Number(formData.get("maximum_context_items") ?? 50),
  });
  if (!response?.ok) redirect(`/reviews/${reviewId}/ai?copilot_error=policy_rejected`);
  revalidatePath(`/reviews/${reviewId}/ai`);
  redirect(`/reviews/${reviewId}/ai?copilot=policy_recorded`);
}

export async function createCopilotQuery(reviewId: string, formData: FormData) {
  const response = await post(`/api/v1/ai/copilot/reviews/${reviewId}/queries`, {
    task_key: String(formData.get("task_key") ?? "PROJECT_STATUS"),
    query: String(formData.get("copilot_query") ?? ""),
  });
  if (!response?.ok) redirect(`/reviews/${reviewId}/ai?copilot_error=query_rejected`);
  revalidatePath(`/reviews/${reviewId}/ai`);
  redirect(`/reviews/${reviewId}/ai?copilot=query_recorded`);
}

export async function decideProposal(
  reviewId: string,
  proposalId: string,
  decision: "ACCEPTED" | "REJECTED",
  formData: FormData,
) {
  const response = await post(`/api/v1/ai/proposals/${proposalId}/decision`, {
    review_id: reviewId,
    decision,
    reason: String(formData.get("reason") ?? "") || null,
  });
  if (!response?.ok) redirect(`/reviews/${reviewId}/ai?proposal=${proposalId}&error=decision_rejected`);
  revalidatePath(`/reviews/${reviewId}/ai`);
  redirect(`/reviews/${reviewId}/ai?proposal=${proposalId}&updated=decision_recorded`);
}

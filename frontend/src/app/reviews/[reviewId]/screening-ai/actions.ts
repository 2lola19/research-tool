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

export async function setAIScreeningPolicy(reviewId: string, formData: FormData) {
  const response = await post(`/api/v1/ai/screening/reviews/${reviewId}/policy`, {
    mode: String(formData.get("mode") ?? "OFF"),
    maximum_batch_size: Number(formData.get("maximum_batch_size") ?? 20),
  });
  if (!response?.ok) redirect(`/reviews/${reviewId}/screening-ai?error=policy_rejected`);
  revalidatePath(`/reviews/${reviewId}/screening-ai`);
  redirect(`/reviews/${reviewId}/screening-ai?updated=policy_saved`);
}

export async function generateAIScreeningSuggestion(
  reviewId: string,
  roundId: string,
  assignmentId: string,
) {
  const response = await post(`/api/v1/ai/screening/reviews/${reviewId}/suggestions`, {
    assignment_ids: [assignmentId],
  });
  if (!response?.ok) {
    redirect(`/reviews/${reviewId}/screening-ai?round=${roundId}&error=suggestion_rejected`);
  }
  revalidatePath(`/reviews/${reviewId}/screening-ai`);
  redirect(`/reviews/${reviewId}/screening-ai?round=${roundId}&updated=suggestion_created`);
}

export async function createAIScreeningEvaluationDataset(reviewId: string, formData: FormData) {
  const response = await post(`/api/v1/ai/screening/reviews/${reviewId}/evaluation-datasets`, {
    logical_key: String(formData.get("logical_key") ?? "screening-evaluation"),
    name: String(formData.get("name") ?? "Screening evaluation"),
    reference_standard: "ADJUDICATED_TITLE_ABSTRACT",
    cases: [
      {
        article_id: String(formData.get("article_id") ?? ""),
        reference_decision: String(formData.get("reference_decision") ?? "RETAIN"),
        reference_source_type: "ADJUDICATED_TITLE_ABSTRACT",
      },
    ],
  });
  if (!response?.ok) redirect(`/reviews/${reviewId}/screening-ai?error=dataset_rejected`);
  revalidatePath(`/reviews/${reviewId}/screening-ai`);
  redirect(`/reviews/${reviewId}/screening-ai?updated=dataset_created`);
}

export async function evaluateAIScreeningDataset(reviewId: string, datasetId: string) {
  const response = await post(
    `/api/v1/ai/screening/reviews/${reviewId}/evaluation-datasets/${datasetId}/evaluate`,
    { evaluation_policy: "CONSERVATIVE" },
  );
  if (!response?.ok) redirect(`/reviews/${reviewId}/screening-ai?error=evaluation_rejected`);
  revalidatePath(`/reviews/${reviewId}/screening-ai`);
  redirect(`/reviews/${reviewId}/screening-ai?updated=evaluation_created`);
}

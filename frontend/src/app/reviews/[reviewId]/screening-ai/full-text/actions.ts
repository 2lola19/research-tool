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

export async function generateFullTextSuggestion(reviewId: string, formData: FormData) {
  const assignmentId = String(formData.get("assignment_id") ?? "");
  const response = await post(
    `/api/v1/ai/screening/full-text/reviews/${reviewId}/suggestions`,
    {
      protocol_version_id: String(formData.get("protocol_version_id") ?? "") || null,
      items: [
        {
          assignment_id: assignmentId,
          document_id: String(formData.get("document_id") ?? ""),
          document_role: String(formData.get("document_role") ?? "PRIMARY_FULL_TEXT"),
        },
      ],
    },
  );
  if (!response?.ok) redirect(`/reviews/${reviewId}/screening-ai/full-text?error=generate`);
  const items = (await response.json()) as Array<{ status: string; failure_reason?: string }>;
  if (items[0]?.status !== "SUCCEEDED") {
    redirect(`/reviews/${reviewId}/screening-ai/full-text?error=readiness`);
  }
  revalidatePath(`/reviews/${reviewId}/screening-ai/full-text`);
  redirect(
    `/reviews/${reviewId}/screening-ai/full-text?assignment=${encodeURIComponent(assignmentId)}&updated=generated`,
  );
}

export async function acceptFullTextSuggestion(
  reviewId: string,
  proposalId: string,
  assignmentId: string,
  formData: FormData,
) {
  const response = await post(
    `/api/v1/ai/screening/full-text/reviews/${reviewId}/proposals/${proposalId}/accept`,
    { exclusion_reason: String(formData.get("exclusion_reason") ?? "") || null },
  );
  if (!response?.ok) redirect(`/reviews/${reviewId}/screening-ai/full-text?error=accept`);
  revalidatePath(`/reviews/${reviewId}/screening-ai/full-text`);
  redirect(
    `/reviews/${reviewId}/screening-ai/full-text?assignment=${encodeURIComponent(assignmentId)}&updated=accepted`,
  );
}

export async function createFullTextDataset(reviewId: string, formData: FormData) {
  const decision = String(formData.get("reference_decision") ?? "RETAIN");
  const response = await post(
    `/api/v1/ai/screening/full-text/reviews/${reviewId}/evaluation-datasets`,
    {
      logical_key: String(formData.get("logical_key") ?? "full-text-evaluation"),
      name: String(formData.get("name") ?? "Full-text evaluation"),
      protocol_version_id: String(formData.get("protocol_version_id") ?? "") || null,
      reference_standard: "CURATED_DATASET",
      cases: [
        {
          document_id: String(formData.get("document_id") ?? ""),
          reference_decision: decision,
          reference_exclusion_criterion_id:
            decision === "EXCLUDE"
              ? String(formData.get("reference_criterion_id") ?? "") || null
              : null,
          reference_source_type: "CURATED_DATASET",
        },
      ],
    },
  );
  if (!response?.ok) redirect(`/reviews/${reviewId}/screening-ai/full-text?error=dataset`);
  revalidatePath(`/reviews/${reviewId}/screening-ai/full-text`);
  redirect(`/reviews/${reviewId}/screening-ai/full-text?updated=dataset`);
}

export async function evaluateFullTextDataset(reviewId: string, datasetId: string) {
  const response = await post(
    `/api/v1/ai/screening/full-text/reviews/${reviewId}/evaluation-datasets/${datasetId}/evaluate`,
    { evaluation_policy: "CONSERVATIVE" },
  );
  if (!response?.ok) redirect(`/reviews/${reviewId}/screening-ai/full-text?error=evaluation`);
  revalidatePath(`/reviews/${reviewId}/screening-ai/full-text`);
  redirect(`/reviews/${reviewId}/screening-ai/full-text?updated=evaluation`);
}

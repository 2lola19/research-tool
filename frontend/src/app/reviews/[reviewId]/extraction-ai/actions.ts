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

export async function setExtractionPolicy(reviewId: string, formData: FormData) {
  const response = await post(`/api/v1/ai/extraction/reviews/${reviewId}/policies`, {
    mode: String(formData.get("mode") ?? "OFF"),
    maximum_batch_size: Number(formData.get("maximum_batch_size") ?? 20),
  });
  if (!response?.ok) redirect(`/reviews/${reviewId}/extraction-ai?error=policy`);
  revalidatePath(`/reviews/${reviewId}/extraction-ai`);
  redirect(`/reviews/${reviewId}/extraction-ai?updated=policy`);
}

export async function generateExtractionProposal(reviewId: string, formData: FormData) {
  const assignmentId = String(formData.get("assignment_id") ?? "");
  const documents = String(formData.get("document_ids") ?? "")
    .split(",")
    .map((id) => id.trim())
    .filter(Boolean)
    .map((document_id, index) => ({
      document_id,
      document_role: index === 0 ? "PRIMARY_FULL_TEXT" : "SUPPLEMENT",
    }));
  const response = await post(`/api/v1/ai/extraction/reviews/${reviewId}/proposals`, {
    items: [{ assignment_id: assignmentId, documents }],
  });
  if (!response?.ok) redirect(`/reviews/${reviewId}/extraction-ai?error=generate`);
  const result = (await response.json()) as Array<{ status: string }>;
  if (result[0]?.status !== "SUCCEEDED") {
    redirect(`/reviews/${reviewId}/extraction-ai?error=readiness`);
  }
  revalidatePath(`/reviews/${reviewId}/extraction-ai`);
  redirect(
    `/reviews/${reviewId}/extraction-ai?assignment=${encodeURIComponent(assignmentId)}&updated=generated`,
  );
}

export async function reviewExtractionField(
  reviewId: string,
  proposalId: string,
  fieldId: string,
  assignmentId: string,
  action: "ACCEPTED" | "EDITED" | "REJECTED" | "UNRESOLVED",
  formData: FormData,
) {
  let humanValue: Record<string, unknown> | null = null;
  if (action === "EDITED") {
    try {
      humanValue = JSON.parse(String(formData.get("human_value") ?? "{}")) as Record<
        string,
        unknown
      >;
    } catch {
      redirect(`/reviews/${reviewId}/extraction-ai?assignment=${assignmentId}&error=json`);
    }
  }
  const response = await post(
    `/api/v1/ai/extraction/reviews/${reviewId}/proposals/${proposalId}/fields/${encodeURIComponent(fieldId)}/review`,
    {
      action,
      human_value: humanValue,
      reason: String(formData.get("reason") ?? "") || null,
    },
  );
  if (!response?.ok) {
    redirect(`/reviews/${reviewId}/extraction-ai?assignment=${assignmentId}&error=review`);
  }
  revalidatePath(`/reviews/${reviewId}/extraction-ai`);
  redirect(`/reviews/${reviewId}/extraction-ai?assignment=${assignmentId}&updated=reviewed`);
}

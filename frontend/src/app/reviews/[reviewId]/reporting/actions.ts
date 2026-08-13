"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

async function post(path: string, body: Record<string, unknown>): Promise<Response | null> {
  const cookieStore = await cookies();
  const token = cookieStore.get("review_access_token")?.value;
  const organizationId = cookieStore.get("review_organization_id")?.value;
  if (!token || !organizationId) redirect("/login");
  try {
    return await fetch((process.env.API_BASE_URL ?? "http://localhost:8000") + path, {
      method: "POST",
      cache: "no-store",
      headers: {
        Accept: "application/json",
        Authorization: "Bearer " + token,
        "Content-Type": "application/json",
        "X-Organization-ID": organizationId,
      },
      body: JSON.stringify(body),
    });
  } catch {
    return null;
  }
}

export async function generateReport(reviewId: string, formData: FormData) {
  const reportType = String(formData.get("report_type") ?? "STRUCTURED_REVIEW_REPORT");
  const formats =
    reportType === "REPRODUCIBILITY_PACKAGE"
      ? ["ZIP"]
      : String(formData.get("formats") ?? "JSON")
          .split(",")
          .map((item) => item.trim().toUpperCase())
          .filter(Boolean);
  const specification = await post("/api/v1/reporting/specifications", {
    review_id: reviewId,
    logical_key: reportType,
    report_type: reportType,
    definition: { formats, allow_draft: formData.get("allow_draft") === "on" },
  });
  if (!specification?.ok) redirect(`/reviews/${reviewId}/reporting?error=specification_rejected`);
  const item = (await specification.json()) as { id: string };
  const generated = await post(`/api/v1/reporting/specifications/${item.id}/generate`, {
    review_id: reviewId,
  });
  if (!generated?.ok) redirect(`/reviews/${reviewId}/reporting?error=generation_rejected`);
  revalidatePath(`/reviews/${reviewId}/reporting`);
  redirect(`/reviews/${reviewId}/reporting?updated=report_generated`);
}


"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

const exportFormats = new Set(["CSV", "XLSX", "JSON", "RIS"]);

export async function createExport(reviewId: string, formData: FormData) {
  const format = String(formData.get("format") ?? "");
  if (!exportFormats.has(format)) {
    redirect(`/reviews/${reviewId}/reports?error=invalid_format`);
  }
  const cookieStore = await cookies();
  const accessToken = cookieStore.get("review_access_token")?.value;
  const organizationId = cookieStore.get("review_organization_id")?.value;
  if (!accessToken || !organizationId) {
    redirect("/login");
  }
  const apiBaseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl}/api/v1/exports/reviews/${reviewId}`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
        "X-Organization-ID": organizationId,
      },
      body: JSON.stringify({ format }),
      cache: "no-store",
    });
  } catch {
    redirect(`/reviews/${reviewId}/reports?error=service_unavailable`);
  }
  if (response.status === 401 || response.status === 403) {
    redirect("/login?error=session_expired");
  }
  if (!response.ok) {
    redirect(`/reviews/${reviewId}/reports?error=export_failed`);
  }
  revalidatePath(`/reviews/${reviewId}/reports`);
  redirect(`/reviews/${reviewId}/reports?created=${format.toLowerCase()}`);
}

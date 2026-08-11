"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

type Session = { accessToken: string; organizationId: string };

async function session(): Promise<Session> {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get("review_access_token")?.value;
  const organizationId = cookieStore.get("review_organization_id")?.value;
  if (!accessToken || !organizationId) {
    redirect("/login");
  }
  return { accessToken, organizationId };
}

async function post(path: string, body: Record<string, unknown>): Promise<Response | null> {
  const { accessToken, organizationId } = await session();
  const apiBaseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  try {
    return await fetch(`${apiBaseUrl}${path}`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
        "X-Organization-ID": organizationId,
      },
      body: JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    return null;
  }
}

function required(formData: FormData, name: string): string {
  return String(formData.get(name) ?? "").trim();
}

function optional(formData: FormData, name: string): string | null {
  return required(formData, name) || null;
}

function resultCount(formData: FormData): number | null {
  const value = optional(formData, "provider_result_count");
  return value === null ? null : Number(value);
}

export async function createIdentificationSource(reviewId: string, formData: FormData) {
  const response = await post("/api/v1/search-executions/sources", {
    review_id: reviewId,
    source_key: required(formData, "source_key"),
    display_name: required(formData, "display_name"),
    classification: required(formData, "classification"),
    provider_name: required(formData, "provider_name"),
    platform_name: optional(formData, "platform_name"),
  });
  if (!response) redirect(`/reviews/${reviewId}/search?error=service_unavailable`);
  if (response.status === 401 || response.status === 403) redirect("/login?error=session_expired");
  if (!response.ok) redirect(`/reviews/${reviewId}/search?error=source_creation_failed`);
  revalidatePath(`/reviews/${reviewId}/search`);
  redirect(`/reviews/${reviewId}/search?created=source`);
}

export async function createSearchExecution(reviewId: string, formData: FormData) {
  const executedAt = required(formData, "executed_at_utc");
  const restrictions = optional(formData, "restrictions");
  const response = await post("/api/v1/search-executions", {
    review_id: reviewId,
    source_id: required(formData, "source_id"),
    search_strategy_version_id: optional(formData, "search_strategy_version_id"),
    method: required(formData, "method"),
    exact_query: optional(formData, "exact_query"),
    filters: restrictions ? { restrictions } : {},
    executed_at: `${executedAt}:00+00:00`,
    software_version: optional(formData, "software_version"),
    status: required(formData, "status"),
    provider_result_count: resultCount(formData),
  });
  if (!response) redirect(`/reviews/${reviewId}/search?error=service_unavailable`);
  if (response.status === 401 || response.status === 403) redirect("/login?error=session_expired");
  if (!response.ok) redirect(`/reviews/${reviewId}/search?error=execution_creation_failed`);
  const execution = (await response.json()) as { id: string };
  const importBatchId = optional(formData, "import_batch_id");
  if (importBatchId) {
    const linkResponse = await post(`/api/v1/search-executions/${execution.id}/imports`, {
      review_id: reviewId,
      import_batch_id: importBatchId,
    });
    if (!linkResponse?.ok) redirect(`/reviews/${reviewId}/search?error=import_link_failed`);
  }
  revalidatePath(`/reviews/${reviewId}/search`);
  redirect(`/reviews/${reviewId}/search?created=execution`);
}

export async function linkSearchImport(
  reviewId: string,
  executionId: string,
  formData: FormData,
) {
  const response = await post(`/api/v1/search-executions/${executionId}/imports`, {
    review_id: reviewId,
    import_batch_id: required(formData, "import_batch_id"),
  });
  if (!response) redirect(`/reviews/${reviewId}/search?error=service_unavailable`);
  if (response.status === 401 || response.status === 403) redirect("/login?error=session_expired");
  if (!response.ok) redirect(`/reviews/${reviewId}/search?error=import_link_failed`);
  revalidatePath(`/reviews/${reviewId}/search`);
  redirect(`/reviews/${reviewId}/search?created=link`);
}

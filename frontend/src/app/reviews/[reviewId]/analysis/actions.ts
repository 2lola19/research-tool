"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

async function post(path: string, body: Record<string, unknown>): Promise<Response | null> {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get("review_access_token")?.value;
  const organizationId = cookieStore.get("review_organization_id")?.value;
  if (!accessToken || !organizationId) redirect("/login");
  try {
    return await fetch(`${process.env.API_BASE_URL ?? "http://localhost:8000"}${path}`, {
      method: "POST",
      cache: "no-store",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
        "X-Organization-ID": organizationId,
      },
      body: JSON.stringify(body),
    });
  } catch {
    return null;
  }
}

function value(formData: FormData, key: string): string {
  return String(formData.get(key) ?? "").trim();
}

function optional(formData: FormData, key: string): string | null {
  return value(formData, key) || null;
}

function values(formData: FormData, key: string): string[] {
  return value(formData, key)
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

async function finish(reviewId: string, response: Response | null, success: string): Promise<never> {
  if (!response) redirect(`/reviews/${reviewId}/analysis?error=service_unavailable`);
  if (response.status === 401 || response.status === 403) redirect("/login?error=session_expired");
  if (!response.ok) redirect(`/reviews/${reviewId}/analysis?error=scientific_write_rejected`);
  revalidatePath(`/reviews/${reviewId}/analysis`);
  redirect(`/reviews/${reviewId}/analysis?updated=${success}`);
}

export async function createSpecification(reviewId: string, formData: FormData) {
  const model = value(formData, "model");
  const measure = value(formData, "effect_measure");
  const response = await post("/api/v1/analysis/specifications-with-version", {
    review_id: reviewId,
    key: value(formData, "key"),
    definition: {
      outcome_version_id: value(formData, "outcome_version_id"),
      timepoint_window_id: optional(formData, "timepoint_window_id"),
      synthesis_population: value(formData, "synthesis_population"),
      intervention: value(formData, "intervention"),
      comparator: value(formData, "comparator"),
      eligible_study_designs: values(formData, "eligible_study_designs"),
      effect_measure: measure,
      model,
      heterogeneity_estimator: model === "RANDOM_EFFECTS" ? "DERSIMONIAN_LAIRD" : "NONE",
      confidence_level: value(formData, "confidence_level"),
      transformation: ["RR", "OR", "HR"].includes(measure) ? "LOG" : "IDENTITY",
      ci_method: "NORMAL",
      zero_event_policy: value(formData, "zero_event_policy"),
      missing_variance_policy: "BLOCK",
      adjustment_policy: value(formData, "adjustment_policy"),
      analysis_population: value(formData, "analysis_population"),
      selection_policy: "EXPLICIT_ESTIMATE_IDS",
      multi_arm_policy: "BLOCK",
      cluster_policy: "BLOCK",
      crossover_policy: "BLOCK",
      minimum_studies: Number(value(formData, "minimum_studies")),
      prediction_interval: formData.get("prediction_interval") === "on",
      standardized_effect_definition: optional(formData, "standardized_effect_definition"),
    },
  });
  await finish(reviewId, response, "analysis_specification_created");
}

export async function createAnalysisSet(reviewId: string, formData: FormData) {
  const response = await post("/api/v1/analysis/sets", {
    review_id: reviewId,
    specification_version_id: value(formData, "specification_version_id"),
    candidate_set_id: value(formData, "candidate_set_id"),
    selected_estimate_ids: values(formData, "selected_estimate_ids"),
  });
  await finish(reviewId, response, "analysis_set_created");
}

export async function executeAnalysis(reviewId: string, analysisSetId: string) {
  const response = await post("/api/v1/analysis/runs", {
    review_id: reviewId,
    analysis_set_id: analysisSetId,
  });
  await finish(reviewId, response, "meta_analysis_completed");
}

export async function generateForestPlot(reviewId: string, runId: string) {
  const response = await post(`/api/v1/analysis/runs/${runId}/forest-plot`, {
    review_id: reviewId,
  });
  await finish(reviewId, response, "forest_plot_generated");
}

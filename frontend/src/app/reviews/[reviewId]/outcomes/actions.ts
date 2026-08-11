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

function value(formData: FormData, key: string): string {
  return String(formData.get(key) ?? "").trim();
}

function optional(formData: FormData, key: string): string | null {
  return value(formData, key) || null;
}

async function finish(
  reviewId: string,
  response: Response | null,
  success: string,
): Promise<never> {
  if (!response) redirect(`/reviews/${reviewId}/outcomes?error=service_unavailable`);
  if (response.status === 401 || response.status === 403) redirect("/login?error=session_expired");
  if (!response.ok) redirect(`/reviews/${reviewId}/outcomes?error=scientific_write_rejected`);
  revalidatePath(`/reviews/${reviewId}/outcomes`);
  redirect(`/reviews/${reviewId}/outcomes?updated=${success}`);
}

export async function createTimepointWindow(reviewId: string, formData: FormData) {
  const response = await post("/api/v1/outcomes/timepoint-windows", {
    review_id: reviewId,
    key: value(formData, "key"),
    label: value(formData, "label"),
    anchor: value(formData, "anchor"),
    minimum_days: optional(formData, "minimum_days"),
    maximum_days: optional(formData, "maximum_days"),
    rule_version: value(formData, "rule_version") || "1",
  });
  await finish(reviewId, response, "timepoint_window_created");
}

export async function createUnit(reviewId: string, formData: FormData) {
  const response = await post("/api/v1/outcomes/units", {
    review_id: reviewId,
    key: value(formData, "key"),
    label: value(formData, "label"),
    dimension: value(formData, "dimension"),
    context_key: value(formData, "context_key") || "GENERAL",
    base_unit_key: value(formData, "base_unit_key"),
    multiplier_to_base: value(formData, "multiplier_to_base") || "1",
    offset_to_base: value(formData, "offset_to_base") || "0",
    precision: Number(value(formData, "precision") || "6"),
    rule_version: value(formData, "rule_version") || "1",
  });
  await finish(reviewId, response, "unit_created");
}

export async function createScale(reviewId: string, formData: FormData) {
  const response = await post("/api/v1/outcomes/measurement-scales", {
    review_id: reviewId,
    key: value(formData, "key"),
    name: value(formData, "name"),
    minimum: optional(formData, "minimum"),
    maximum: optional(formData, "maximum"),
    directionality: value(formData, "directionality"),
  });
  await finish(reviewId, response, "measurement_scale_created");
}

export async function createOutcome(reviewId: string, formData: FormData) {
  const windowId = optional(formData, "timepoint_window_id");
  const response = await post("/api/v1/outcomes/definitions-with-version", {
    review_id: reviewId,
    key: value(formData, "key"),
    protocol_version_id: optional(formData, "protocol_version_id"),
    definition: {
      name: value(formData, "name"),
      description: optional(formData, "description"),
      outcome_type: value(formData, "outcome_type"),
      directionality: value(formData, "directionality"),
      role: value(formData, "role"),
      compatible_effect_measures: value(formData, "compatible_effect_measures")
        .split(",")
        .map((item) => item.trim().toUpperCase())
        .filter(Boolean),
      expected_timepoint_window_ids: windowId ? [windowId] : [],
    },
  });
  await finish(reviewId, response, "outcome_created");
}

export async function createMapping(reviewId: string, formData: FormData) {
  const response = await post("/api/v1/outcomes/mappings", {
    review_id: reviewId,
    study_id: value(formData, "study_id"),
    extraction_value_id: value(formData, "extraction_value_id"),
    outcome_version_id: value(formData, "outcome_version_id"),
    method: "MANUAL",
    rationale: value(formData, "rationale"),
    reported_unit_id: optional(formData, "reported_unit_id"),
    normalized_unit_id: optional(formData, "normalized_unit_id"),
    reported_time_value: optional(formData, "reported_time_value"),
    reported_time_unit: optional(formData, "reported_time_unit"),
    reported_time_anchor: optional(formData, "reported_time_anchor"),
    timepoint_window_id: optional(formData, "timepoint_window_id"),
    measurement_scale_id: optional(formData, "measurement_scale_id"),
    direction_transformation: value(formData, "direction_transformation") || "NONE",
    transformation_reason: optional(formData, "transformation_reason"),
  });
  await finish(reviewId, response, "outcome_mapped");
}

export async function deriveEffect(reviewId: string, formData: FormData) {
  const component = (name: string) => optional(formData, name);
  const components = Object.fromEntries(
    [
      "events_intervention",
      "sample_intervention",
      "events_comparator",
      "sample_comparator",
      "mean_intervention",
      "sd_intervention",
      "mean_comparator",
      "sd_comparator",
    ]
      .map((name) => [name, component(name)])
      .filter((entry): entry is [string, string] => entry[1] !== null),
  );
  const response = await post("/api/v1/outcomes/effect-estimates", {
    review_id: reviewId,
    study_id: value(formData, "study_id"),
    outcome_version_id: value(formData, "outcome_version_id"),
    effect_measure: value(formData, "effect_measure"),
    origin: "DERIVED",
    adjustment: value(formData, "adjustment"),
    analysis_population: value(formData, "analysis_population"),
    timepoint_window_id: optional(formData, "timepoint_window_id"),
    unit_id: optional(formData, "unit_id"),
    measurement_scale_id: optional(formData, "measurement_scale_id"),
    components,
    source_mapping_ids: [value(formData, "source_mapping_id")],
  });
  await finish(reviewId, response, "effect_derived");
}

export async function createCandidate(reviewId: string, formData: FormData) {
  const response = await post("/api/v1/outcomes/candidate-sets", {
    review_id: reviewId,
    outcome_version_id: value(formData, "outcome_version_id"),
    effect_measure: value(formData, "effect_measure"),
    timepoint_window_id: optional(formData, "timepoint_window_id"),
    population_label: optional(formData, "population_label"),
    estimate_ids: value(formData, "estimate_ids")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
  });
  await finish(reviewId, response, "candidate_created");
}

export async function evaluateCandidate(reviewId: string, candidateId: string) {
  const response = await post(`/api/v1/outcomes/candidate-sets/${candidateId}/evaluate`, {
    review_id: reviewId,
  });
  await finish(reviewId, response, "readiness_evaluated");
}

"use server";

import { revalidatePath } from "next/cache";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

async function request(
  method: "POST" | "PUT",
  path: string,
  body: Record<string, unknown>,
): Promise<Response | null> {
  const cookieStore = await cookies();
  const accessToken = cookieStore.get("review_access_token")?.value;
  const organizationId = cookieStore.get("review_organization_id")?.value;
  if (!accessToken || !organizationId) redirect("/login");
  try {
    return await fetch((process.env.API_BASE_URL ?? "http://localhost:8000") + path, {
      method,
      cache: "no-store",
      headers: {
        Accept: "application/json",
        Authorization: "Bearer " + accessToken,
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

function list(formData: FormData, key: string): string[] {
  return value(formData, key)
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

async function finish(reviewId: string, response: Response | null, success: string): Promise<never> {
  if (!response) redirect("/reviews/" + reviewId + "/certainty?error=service_unavailable");
  if (response.status === 401 || response.status === 403) {
    redirect("/login?error=session_expired");
  }
  if (!response.ok) {
    redirect("/reviews/" + reviewId + "/certainty?error=scientific_write_rejected");
  }
  revalidatePath("/reviews/" + reviewId + "/certainty");
  redirect("/reviews/" + reviewId + "/certainty?updated=" + success);
}

export async function installFoundation(reviewId: string) {
  const response = await request("POST", "/api/v1/certainty/foundation-framework", {
    review_id: reviewId,
  });
  await finish(reviewId, response, "foundation_framework_installed");
}

export async function createAssessment(reviewId: string, formData: FormData) {
  const analysisTarget = value(formData, "analysis_target").split("|");
  const runId = analysisTarget[0] || null;
  const specificationVersionId = analysisTarget[1] || null;
  const response = await request("POST", "/api/v1/certainty/assessments", {
    review_id: reviewId,
    outcome_version_id: value(formData, "outcome_version_id"),
    timepoint_window_id: optional(formData, "timepoint_window_id"),
    analysis_specification_version_id: specificationVersionId,
    meta_analysis_run_id: runId,
    framework_version_id: value(formData, "framework_version_id"),
    threshold_version_id: optional(formData, "threshold_version_id"),
    round_number: Number(value(formData, "round_number") || "1"),
    evidence_body_type: value(formData, "evidence_body_type"),
    evidence_body: {
      study_ids: list(formData, "study_ids"),
      publication_bias_evidence: {
        note: optional(formData, "publication_bias_note"),
      },
    },
    starting_certainty: value(formData, "starting_certainty"),
    starting_rationale: value(formData, "starting_rationale"),
    supersedes_assessment_id: optional(formData, "supersedes_assessment_id"),
  });
  await finish(reviewId, response, "certainty_assessment_created");
}

export async function saveDomain(
  reviewId: string,
  assessmentId: string,
  domainKey: string,
  formData: FormData,
) {
  const response = await request(
    "PUT",
    "/api/v1/certainty/assessments/" + assessmentId + "/domains/" + domainKey,
    {
      review_id: reviewId,
      judgment: value(formData, "judgment"),
      rationale: value(formData, "rationale"),
      evidence_location_id: optional(formData, "evidence_location_id"),
      evidence: { note: optional(formData, "evidence_note") },
    },
  );
  await finish(reviewId, response, "certainty_domain_saved");
}

export async function saveFinal(reviewId: string, assessmentId: string, formData: FormData) {
  const response = await request(
    "PUT",
    "/api/v1/certainty/assessments/" + assessmentId + "/final",
    {
      review_id: reviewId,
      final_certainty: value(formData, "final_certainty"),
      final_rationale: value(formData, "final_rationale"),
      override_reason: optional(formData, "override_reason"),
    },
  );
  await finish(reviewId, response, "certainty_final_saved");
}

export async function submitAssessment(reviewId: string, assessmentId: string) {
  const response = await request(
    "POST",
    "/api/v1/certainty/assessments/" + assessmentId + "/submit",
    { review_id: reviewId },
  );
  await finish(reviewId, response, "certainty_assessment_submitted");
}

export async function compareAssessments(reviewId: string, formData: FormData) {
  const response = await request("POST", "/api/v1/certainty/comparisons", {
    review_id: reviewId,
    assessment_a_id: value(formData, "assessment_a_id"),
    assessment_b_id: value(formData, "assessment_b_id"),
  });
  await finish(reviewId, response, "certainty_assessments_revealed");
}

export async function adjudicateComparison(
  reviewId: string,
  comparisonId: string,
  formData: FormData,
) {
  const response = await request(
    "POST",
    "/api/v1/certainty/comparisons/" + comparisonId + "/adjudicate",
    {
      review_id: reviewId,
      resolution_assessment_id: value(formData, "resolution_assessment_id"),
      rationale: value(formData, "rationale"),
      evidence_location_id: optional(formData, "evidence_location_id"),
    },
  );
  await finish(reviewId, response, "certainty_conflict_adjudicated");
}

export async function createSummaryOfFindings(reviewId: string, assessmentId: string) {
  const response = await request(
    "POST",
    "/api/v1/certainty/assessments/" + assessmentId + "/sof-snapshot",
    { review_id: reviewId },
  );
  await finish(reviewId, response, "summary_of_findings_snapshot_created");
}

export async function createAICertaintyPolicy(reviewId: string, formData: FormData) {
  const response = await request("POST", "/api/v1/ai/certainty/reviews/" + reviewId + "/policies", {
    maximum_batch_size: Number(value(formData, "maximum_batch_size") || "20"),
  });
  await finish(reviewId, response, "ai_certainty_policy_saved");
}

export async function requestAICertaintySuggestions(
  reviewId: string,
  assessmentId: string,
  formData: FormData,
) {
  const documentIds = list(formData, "document_ids");
  const response = await request("POST", "/api/v1/ai/certainty/reviews/" + reviewId + "/proposals", {
    items: [
      {
        assessment_id: assessmentId,
        documents: documentIds.map((documentId) => ({
          document_id: documentId,
          document_role: "PRIMARY_FULL_TEXT",
        })),
      },
    ],
  });
  await finish(reviewId, response, "ai_certainty_suggestions_created");
}

export async function reviewAICertaintyProposal(
  reviewId: string,
  proposalId: string,
  formData: FormData,
) {
  const rawPayload = value(formData, "human_payload");
  let humanPayload: Record<string, unknown> | null = null;
  if (rawPayload) {
    try {
      const parsed: unknown = JSON.parse(rawPayload);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        redirect("/reviews/" + reviewId + "/certainty?error=invalid_human_payload");
      }
      humanPayload = parsed as Record<string, unknown>;
    } catch {
      redirect("/reviews/" + reviewId + "/certainty?error=invalid_human_payload");
    }
  }
  const response = await request(
    "POST",
    "/api/v1/ai/certainty/reviews/" + reviewId + "/proposals/" + proposalId + "/review",
    {
      action: value(formData, "action"),
      canonical_action: optional(formData, "canonical_action"),
      human_payload: humanPayload,
      reason: optional(formData, "reason"),
    },
  );
  await finish(reviewId, response, "ai_certainty_proposal_reviewed");
}

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
    return await fetch(`${process.env.API_BASE_URL ?? "http://localhost:8000"}${path}`, {
      method,
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

async function finish(reviewId: string, response: Response | null, success: string) {
  if (!response) redirect(`/reviews/${reviewId}/risk-of-bias?error=service_unavailable`);
  if (response.status === 401 || response.status === 403) redirect("/login?error=session_expired");
  if (!response.ok) redirect(`/reviews/${reviewId}/risk-of-bias?error=scientific_write_rejected`);
  revalidatePath(`/reviews/${reviewId}/risk-of-bias`);
  redirect(`/reviews/${reviewId}/risk-of-bias?updated=${success}`);
}

export async function installDemonstration(reviewId: string) {
  const response = await request("POST", "/api/v1/risk-of-bias/demonstration-instrument", {
    review_id: reviewId,
  });
  await finish(reviewId, response, "instrument_installed");
}

export async function decideVersion(
  reviewId: string,
  versionId: string,
  decision: "APPROVED" | "REJECTED",
) {
  const response = await request(
    "POST",
    `/api/v1/risk-of-bias/instrument-versions/${versionId}/decision`,
    { review_id: reviewId, decision },
  );
  await finish(reviewId, response, "instrument_decided");
}

export async function createAssessment(reviewId: string, formData: FormData) {
  const response = await request("POST", "/api/v1/risk-of-bias/assessments", {
    review_id: reviewId,
    study_id: value(formData, "study_id"),
    instrument_version_id: value(formData, "instrument_version_id"),
    round_number: Number(value(formData, "round_number") || "1"),
  });
  await finish(reviewId, response, "assessment_created");
}

export async function saveAnswer(
  reviewId: string,
  assessmentId: string,
  questionKey: string,
  formData: FormData,
) {
  const response = await request(
    "PUT",
    `/api/v1/risk-of-bias/assessments/${assessmentId}/answers/${questionKey}`,
    {
      review_id: reviewId,
      answer: value(formData, "answer"),
      rationale: optional(formData, "rationale"),
      evidence_location_id: optional(formData, "evidence_location_id"),
    },
  );
  await finish(reviewId, response, "answer_saved");
}

export async function saveDomain(
  reviewId: string,
  assessmentId: string,
  domainKey: string,
  formData: FormData,
) {
  const response = await request(
    "PUT",
    `/api/v1/risk-of-bias/assessments/${assessmentId}/domains/${domainKey}`,
    {
      review_id: reviewId,
      final_judgment: value(formData, "final_judgment"),
      rationale: value(formData, "rationale"),
      override_reason: optional(formData, "override_reason"),
      evidence_location_id: optional(formData, "evidence_location_id"),
    },
  );
  await finish(reviewId, response, "domain_saved");
}

export async function saveOverall(
  reviewId: string,
  assessmentId: string,
  formData: FormData,
) {
  const response = await request(
    "PUT",
    `/api/v1/risk-of-bias/assessments/${assessmentId}/overall`,
    {
      review_id: reviewId,
      final_judgment: value(formData, "final_judgment"),
      rationale: value(formData, "rationale"),
      override_reason: optional(formData, "override_reason"),
      evidence_location_id: optional(formData, "evidence_location_id"),
    },
  );
  await finish(reviewId, response, "overall_saved");
}

export async function submitAssessment(reviewId: string, assessmentId: string) {
  const response = await request(
    "POST",
    `/api/v1/risk-of-bias/assessments/${assessmentId}/submit`,
    { review_id: reviewId },
  );
  await finish(reviewId, response, "assessment_submitted");
}

export async function compareAssessments(reviewId: string, formData: FormData) {
  const response = await request("POST", "/api/v1/risk-of-bias/comparisons", {
    review_id: reviewId,
    assessment_a_id: value(formData, "assessment_a_id"),
    assessment_b_id: value(formData, "assessment_b_id"),
  });
  await finish(reviewId, response, "assessments_compared");
}

export async function adjudicateComparison(
  reviewId: string,
  comparisonId: string,
  formData: FormData,
) {
  const response = await request(
    "POST",
    `/api/v1/risk-of-bias/comparisons/${comparisonId}/adjudicate`,
    {
      review_id: reviewId,
      resolution_assessment_id: value(formData, "resolution_assessment_id"),
      rationale: value(formData, "rationale"),
      evidence_location_id: optional(formData, "evidence_location_id"),
    },
  );
  await finish(reviewId, response, "conflict_adjudicated");
}

export async function createAIRiskOfBiasPolicy(reviewId: string, formData: FormData) {
  const response = await request("POST", `/api/v1/ai/risk-of-bias/reviews/${reviewId}/policies`, {
    mode: value(formData, "mode"),
    maximum_batch_size: Number(value(formData, "maximum_batch_size") || "20"),
  });
  await finish(reviewId, response, "ai_rob_policy_saved");
}

export async function generateAIRiskOfBiasProposal(reviewId: string, formData: FormData) {
  const assessmentId = value(formData, "assessment_id");
  const documents = value(formData, "document_ids")
    .split(/[\s,]+/)
    .filter(Boolean)
    .map((document_id, index) => ({
      document_id,
      document_role: index === 0 ? "PRIMARY_FULL_TEXT" : "SUPPLEMENT",
    }));
  const response = await request("POST", `/api/v1/ai/risk-of-bias/reviews/${reviewId}/proposals`, {
    items: [{ assessment_id: assessmentId, documents }],
  });
  await finish(reviewId, response, "ai_rob_proposal_created");
}

export async function reviewAIRiskOfBiasAnswer(
  reviewId: string,
  proposalId: string,
  questionKey: string,
  formData: FormData,
) {
  const action = value(formData, "action");
  const response = await request(
    "POST",
    `/api/v1/ai/risk-of-bias/reviews/${reviewId}/proposals/${proposalId}/answers/${questionKey}/review`,
    {
      action,
      reason: optional(formData, "reason"),
      human_answer:
        action === "EDITED"
          ? { answer: value(formData, "human_answer"), rationale: value(formData, "reason") }
          : null,
    },
  );
  await finish(reviewId, response, "ai_rob_answer_reviewed");
}

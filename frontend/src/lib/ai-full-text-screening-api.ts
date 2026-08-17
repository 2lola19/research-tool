export type FullTextSuggestion = {
  assignment_id: string;
  article_id: string;
  document_id: string;
  document_version_id: string;
  processing_run_id: string;
  proposal_id: string | null;
  ai_run_id: string | null;
  mode: "OFF" | "BLINDED_AI" | "ASSISTED";
  readiness: string;
  status: string;
  failure_reason: string | null;
  is_revealed: boolean;
  suggestion: "INCLUDE" | "EXCLUDE" | "MAYBE" | "ABSTAIN" | null;
  structured_value: {
    rationale?: string;
    exclusion_criterion_ids?: string[];
    evidence?: Array<{
      document_id: string;
      document_version_id: string;
      chunk_id: string;
      page: number | null;
      section: string | null;
      quoted_text: string;
    }>;
    missing_information?: string[];
    model_reported_confidence?: number | null;
  } | null;
  protocol_version_id: string;
  stale: boolean;
  stale_reasons: string[];
  selected_chunk_ids: string[];
  selection_method: string;
};

export type FullTextDataset = {
  id: string;
  name: string;
  logical_key: string;
  version: number;
  reference_standard: string;
  content_hash: string;
  stage: "FULL_TEXT";
};

export type FullTextEvaluation = {
  id: string;
  dataset_id: string;
  evaluation_policy: string;
  metric_version: string;
  metrics: Record<string, unknown>;
  content_hash: string;
  stage: "FULL_TEXT";
};

export type FullTextCaseResult = {
  id: string;
  proposal_id: string;
  disagreement: string;
  error_classifications: Array<{ category: string; notes: string | null }>;
};

function requestHeaders(token: string, organizationId: string): HeadersInit {
  return {
    Accept: "application/json",
    Authorization: `Bearer ${token}`,
    "X-Organization-ID": organizationId,
  };
}

export async function getFullTextAIWorkspace(
  token: string,
  organizationId: string,
  reviewId: string,
): Promise<{
  datasets: FullTextDataset[];
  evaluations: FullTextEvaluation[];
  caseResults: FullTextCaseResult[];
}> {
  const base = process.env.API_BASE_URL ?? "http://localhost:8000";
  try {
    const [datasets, evaluations] = await Promise.all([
      fetch(`${base}/api/v1/ai/screening/full-text/reviews/${reviewId}/evaluation-datasets`, {
        cache: "no-store",
        headers: requestHeaders(token, organizationId),
      }),
      fetch(`${base}/api/v1/ai/screening/full-text/reviews/${reviewId}/evaluations`, {
        cache: "no-store",
        headers: requestHeaders(token, organizationId),
      }),
    ]);
    if (!datasets.ok || !evaluations.ok) {
      return { datasets: [], evaluations: [], caseResults: [] };
    }
    const datasetItems = (await datasets.json()) as FullTextDataset[];
    const evaluationItems = (await evaluations.json()) as FullTextEvaluation[];
    const latest = evaluationItems[0];
    let caseResults: FullTextCaseResult[] = [];
    if (latest) {
      const response = await fetch(
        `${base}/api/v1/ai/screening/full-text/reviews/${reviewId}/evaluations/${latest.id}/case-results`,
        { cache: "no-store", headers: requestHeaders(token, organizationId) },
      );
      if (response.ok) caseResults = (await response.json()) as FullTextCaseResult[];
    }
    return { datasets: datasetItems, evaluations: evaluationItems, caseResults };
  } catch {
    return { datasets: [], evaluations: [], caseResults: [] };
  }
}

export async function getFullTextSuggestion(
  token: string,
  organizationId: string,
  reviewId: string,
  assignmentId: string,
): Promise<FullTextSuggestion | null> {
  try {
    const response = await fetch(
      `${process.env.API_BASE_URL ?? "http://localhost:8000"}/api/v1/ai/screening/full-text/reviews/${reviewId}/assignments/${assignmentId}/suggestion`,
      { cache: "no-store", headers: requestHeaders(token, organizationId) },
    );
    return response.ok ? ((await response.json()) as FullTextSuggestion) : null;
  } catch {
    return null;
  }
}

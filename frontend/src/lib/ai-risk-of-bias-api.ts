export type AIRiskOfBiasAnswer = {
  question_key: string;
  status: "PROPOSED_ANSWER" | "ABSTAIN";
  answer: string | null;
  evidence: Array<{
    document_id: string;
    document_version_id: string;
    chunk_id: string;
    source_block_id: string;
    page: number | null;
    section: string | null;
    quote: string;
  }>;
  confidence: number | null;
  note: string | null;
};

export type AIRiskOfBiasProposal = {
  assessment_id: string;
  study_id: string;
  instrument_version_id: string;
  proposal_id: string | null;
  ai_run_id: string | null;
  mode: "BLINDED_AI" | "ASSISTED";
  readiness: string;
  status: string;
  failure_reason: string | null;
  is_revealed: boolean;
  structured_value: { answers?: AIRiskOfBiasAnswer[] } | null;
  validation_results: {
    aggregate_valid?: boolean;
    answer_results?: Array<{ question_key: string; valid: boolean; errors: string[] }>;
  } | null;
  domain_suggestions: Record<string, string | null> | null;
  overall_suggestion: string | null;
  stale: boolean;
  stale_reasons: string[];
  source_manifest: Array<{
    article_id: string;
    document_id: string;
    document_version_id: string;
    processing_run_id: string;
    document_role: string;
    parser_name: string;
    parser_version: string;
    parsed_content_hash: string;
  }>;
  selected_chunk_ids: string[];
  omitted_chunk_count: number;
  selection_method: string;
};

export type AIRiskOfBiasDataset = {
  id: string;
  instrument_version_id: string;
  logical_key: string;
  version: number;
  reference_standard: string;
  content_hash: string;
};

export type AIRiskOfBiasEvaluation = {
  id: string;
  dataset_id: string;
  metrics: Record<string, unknown>;
  dimensions: Record<string, unknown>;
  result_hash: string;
};

export type AIRiskOfBiasWorkspace = {
  status: "ready" | "unauthorized" | "unavailable";
  proposals: AIRiskOfBiasProposal[];
  datasets: AIRiskOfBiasDataset[];
  evaluations: AIRiskOfBiasEvaluation[];
};

function requestHeaders(token: string, organizationId: string): HeadersInit {
  return {
    Accept: "application/json",
    Authorization: `Bearer ${token}`,
    "X-Organization-ID": organizationId,
  };
}

export async function getAIRiskOfBiasWorkspace(
  token: string,
  organizationId: string,
  reviewId: string,
): Promise<AIRiskOfBiasWorkspace> {
  const base = `${process.env.API_BASE_URL ?? "http://localhost:8000"}/api/v1/ai/risk-of-bias/reviews/${reviewId}`;
  const headers = requestHeaders(token, organizationId);
  try {
    const responses = await Promise.all(
      ["proposals", "evaluation-datasets", "evaluations"].map((path) =>
        fetch(`${base}/${path}`, { cache: "no-store", headers }),
      ),
    );
    if (responses.some((response) => response.status === 401 || response.status === 403)) {
      return { status: "unauthorized", proposals: [], datasets: [], evaluations: [] };
    }
    if (responses.some((response) => !response.ok)) {
      return { status: "unavailable", proposals: [], datasets: [], evaluations: [] };
    }
    const [proposals, datasets, evaluations] = await Promise.all(
      responses.map((response) => response.json()),
    );
    return {
      status: "ready",
      proposals: proposals as AIRiskOfBiasProposal[],
      datasets: datasets as AIRiskOfBiasDataset[],
      evaluations: evaluations as AIRiskOfBiasEvaluation[],
    };
  } catch {
    return { status: "unavailable", proposals: [], datasets: [], evaluations: [] };
  }
}

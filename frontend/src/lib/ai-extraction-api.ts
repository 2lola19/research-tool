export type ExtractionEvidence = {
  document_id: string;
  document_version_id: string;
  chunk_id: string;
  page: number | null;
  section: string | null;
  table_id?: string | null;
  quote: string;
};

export type ExtractionFieldProposal = {
  field_id: string;
  status: string;
  value: unknown;
  reported_value?: string | null;
  unit?: string | null;
  option_id?: string | null;
  confidence?: number | null;
  note?: string | null;
  evidence: ExtractionEvidence[];
};

export type ExtractionProposal = {
  assignment_id: string;
  study_id: string;
  schema_version_id: string;
  proposal_id: string | null;
  ai_run_id: string | null;
  mode: "OFF" | "BLINDED_AI" | "ASSISTED";
  readiness: string;
  status: string;
  failure_reason: string | null;
  is_revealed: boolean;
  structured_value: { fields?: ExtractionFieldProposal[] } | null;
  validation_results: {
    aggregate_valid?: boolean;
    complete?: boolean;
    field_results?: Array<{ field_id: string; valid: boolean; errors: string[] }>;
  } | null;
  stale: boolean;
  stale_reasons: string[];
  source_manifest: Array<{
    article_id: string;
    document_id: string;
    document_role: string;
    processing_run_id: string;
    parser_name: string;
    parser_version: string;
  }>;
  selected_chunk_ids: string[];
  omitted_chunk_count: number;
  selection_method: string;
};

export type ExtractionEvaluationDataset = {
  id: string;
  schema_version_id: string;
  logical_key: string;
  version: number;
  name: string;
  reference_standard: string;
};

export type ExtractionEvaluation = {
  id: string;
  dataset_id: string;
  metrics: Record<string, unknown>;
  dimensions: Record<string, unknown>;
};

export type ExtractionHighRiskResult = {
  id: string;
  case_id: string;
  proposal_id: string | null;
  classification: string;
  ai_value: unknown;
  reference_value: unknown;
  evidence_valid: boolean;
  error_categories: string[];
  source_location: Record<string, unknown> | null;
};

function headers(token: string, organizationId: string): HeadersInit {
  return {
    Accept: "application/json",
    Authorization: `Bearer ${token}`,
    "X-Organization-ID": organizationId,
  };
}

export async function getExtractionAIWorkspace(
  token: string,
  organizationId: string,
  reviewId: string,
): Promise<{
  status: "ready" | "unauthorized" | "unavailable";
  proposals: ExtractionProposal[];
  datasets: ExtractionEvaluationDataset[];
  evaluations: ExtractionEvaluation[];
  highRisk: ExtractionHighRiskResult[];
}> {
  try {
    const base = `${process.env.API_BASE_URL ?? "http://localhost:8000"}/api/v1/ai/extraction/reviews/${reviewId}`;
    const responses = await Promise.all(
      ["proposals", "evaluation-datasets", "evaluations"].map((path) =>
        fetch(`${base}/${path}`, { cache: "no-store", headers: headers(token, organizationId) }),
      ),
    );
    if (responses.some((response) => response.status === 401 || response.status === 403)) {
      return { status: "unauthorized", proposals: [], datasets: [], evaluations: [], highRisk: [] };
    }
    if (responses.some((response) => !response.ok)) {
      return { status: "unavailable", proposals: [], datasets: [], evaluations: [], highRisk: [] };
    }
    const [proposals, datasets, evaluations] = await Promise.all(
      responses.map((response) => response.json()),
    );
    const latest = (evaluations as ExtractionEvaluation[])[0];
    let highRisk: ExtractionHighRiskResult[] = [];
    if (latest) {
      const response = await fetch(`${base}/evaluations/${latest.id}/high-risk`, {
        cache: "no-store",
        headers: headers(token, organizationId),
      });
      if (response.ok) highRisk = (await response.json()) as ExtractionHighRiskResult[];
    }
    return {
      status: "ready",
      proposals: proposals as ExtractionProposal[],
      datasets: datasets as ExtractionEvaluationDataset[],
      evaluations: evaluations as ExtractionEvaluation[],
      highRisk,
    };
  } catch {
    return { status: "unavailable", proposals: [], datasets: [], evaluations: [], highRisk: [] };
  }
}

export async function getExtractionProposal(
  token: string,
  organizationId: string,
  reviewId: string,
  assignmentId: string,
): Promise<ExtractionProposal | null> {
  try {
    const response = await fetch(
      `${process.env.API_BASE_URL ?? "http://localhost:8000"}/api/v1/ai/extraction/reviews/${reviewId}/assignments/${assignmentId}`,
      { cache: "no-store", headers: headers(token, organizationId) },
    );
    return response.ok ? ((await response.json()) as ExtractionProposal) : null;
  } catch {
    return null;
  }
}

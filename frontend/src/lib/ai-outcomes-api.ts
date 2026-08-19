export type AIOutcomeEvidence = {
  document_id: string;
  document_version_id: string;
  chunk_id: string;
  source_block_id: string;
  page: number | null;
  section: string | null;
  quote: string;
};

export type AIOutcomeProposal = {
  extraction_value_id: string;
  study_id: string;
  outcome_version_id: string;
  proposal_id: string | null;
  ai_run_id: string | null;
  readiness: string;
  status: string;
  failure_reason: string | null;
  structured_value: Record<string, unknown> | null;
  validation_results: {
    aggregate_valid?: boolean;
    errors?: Array<{ code: string; message: string }>;
  } | null;
  stale: boolean;
  stale_reasons: string[];
  source_manifest: Array<Record<string, unknown>>;
  selected_chunk_ids: string[];
  omitted_chunk_count: number;
  selection_method: string;
};

export type AIOutcomeDataset = {
  id: string;
  review_id: string;
  logical_key: string;
  version: number;
  name: string;
  reference_standard: string;
  content_hash: string;
};

export type AIOutcomeEvaluation = {
  id: string;
  review_id: string;
  dataset_id: string;
  metrics: Record<string, unknown>;
  dimensions: Record<string, unknown>;
  case_results: Array<Record<string, unknown>>;
  result_hash: string;
};

export type AIOutcomeWorkspace = {
  status: "ready" | "unauthorized" | "unavailable";
  proposals: AIOutcomeProposal[];
  datasets: AIOutcomeDataset[];
  evaluations: AIOutcomeEvaluation[];
};

export async function getAIOutcomeWorkspace(
  token: string,
  organizationId: string,
  reviewId: string,
): Promise<AIOutcomeWorkspace> {
  const base = `${process.env.API_BASE_URL ?? "http://localhost:8000"}/api/v1/ai/outcomes/reviews/${reviewId}`;
  const headers = {
    Accept: "application/json",
    Authorization: `Bearer ${token}`,
    "X-Organization-ID": organizationId,
  };
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
      proposals: proposals as AIOutcomeProposal[],
      datasets: datasets as AIOutcomeDataset[],
      evaluations: evaluations as AIOutcomeEvaluation[],
    };
  } catch {
    return { status: "unavailable", proposals: [], datasets: [], evaluations: [] };
  }
}

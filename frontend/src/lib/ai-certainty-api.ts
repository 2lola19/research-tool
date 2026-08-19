export type AICertaintyEvidence = {
  document_id: string;
  document_version_id: string;
  chunk_id: string;
  source_block_id: string;
  page: number | null;
  section: string | null;
  quote: string;
};

export type AICertaintyDomainSuggestion = {
  domain_key: string;
  direction: string;
  judgment: string;
  magnitude: number;
  rationale: string;
  evidence: AICertaintyEvidence[];
};

export type AICertaintyStructuredValue = {
  assessment_id: string;
  outcome_version_id: string;
  framework_version_id: string;
  evidence_summary: string;
  evidence: AICertaintyEvidence[];
  domain_suggestions: AICertaintyDomainSuggestion[];
  confidence: number;
  abstention: boolean;
  abstention_reason: string | null;
};

export type AICertaintyProposal = {
  assessment_id: string;
  outcome_version_id: string;
  framework_version_id: string;
  proposal_id: string | null;
  ai_run_id: string | null;
  readiness: string;
  status: string;
  failure_reason: string | null;
  structured_value: AICertaintyStructuredValue | null;
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

export type AICertaintyWorkspace = {
  status: "ready" | "unauthorized" | "unavailable";
  proposals: AICertaintyProposal[];
};

export async function getAICertaintyProposals(
  token: string,
  organizationId: string,
  reviewId: string,
): Promise<AICertaintyWorkspace> {
  const base = `${process.env.API_BASE_URL ?? "http://localhost:8000"}/api/v1/ai/certainty/reviews/${reviewId}`;
  try {
    const response = await fetch(`${base}/proposals`, {
      cache: "no-store",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${token}`,
        "X-Organization-ID": organizationId,
      },
    });
    if (response.status === 401 || response.status === 403) {
      return { status: "unauthorized", proposals: [] };
    }
    if (!response.ok) {
      return { status: "unavailable", proposals: [] };
    }
    return { status: "ready", proposals: (await response.json()) as AICertaintyProposal[] };
  } catch {
    return { status: "unavailable", proposals: [] };
  }
}

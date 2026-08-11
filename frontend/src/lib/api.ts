export type BackendHealth = {
  status: "healthy" | "unhealthy" | "unavailable";
  checks?: Record<string, "up" | "down"> | null;
};

export async function getBackendHealth(): Promise<BackendHealth> {
  const apiBaseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  try {
    const response = await fetch(`${apiBaseUrl}/health/ready`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      return { status: "unhealthy", checks: { api: "down" } };
    }
    return (await response.json()) as BackendHealth;
  } catch {
    return { status: "unavailable", checks: { api: "down" } };
  }
}

export type ReviewProject = {
  id: string;
  organization_id: string;
  title: string;
  project_slug: string;
  description: string | null;
  owner_user_id: string;
  created_by_user_id: string;
  archived: boolean;
  archived_by_user_id: string | null;
};

export type ReviewProjectResult =
  | { status: "ready"; projects: ReviewProject[] }
  | { status: "unauthorized"; projects: [] }
  | { status: "unavailable"; projects: [] };

export async function getReviewProjects(
  accessToken: string,
  organizationId: string,
): Promise<ReviewProjectResult> {
  const apiBaseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  try {
    const response = await fetch(`${apiBaseUrl}/api/v1/reviews`, {
      cache: "no-store",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${accessToken}`,
        "X-Organization-ID": organizationId,
      },
    });
    if (response.status === 401 || response.status === 403) {
      return { status: "unauthorized", projects: [] };
    }
    if (!response.ok) {
      return { status: "unavailable", projects: [] };
    }
    return { status: "ready", projects: (await response.json()) as ReviewProject[] };
  } catch {
    return { status: "unavailable", projects: [] };
  }
}

export type PrismaBlocker = {
  code: string;
  message: string;
  count: number | null;
};

export type PrismaSummary = {
  counts: Record<string, number | Record<string, number> | null>;
  readiness: { ready_for_final: boolean; blockers: PrismaBlocker[] };
  source_references: Record<string, unknown>;
};

export type ExportArtifact = {
  id: string;
  review_id: string;
  prisma_snapshot_id: string;
  format: "CSV" | "XLSX" | "JSON" | "RIS";
  filename: string;
  sha256: string;
  byte_size: number;
  manifest: Record<string, unknown>;
  created_at: string;
};

export type ReviewReportResult =
  | { status: "ready"; summary: PrismaSummary; exports: ExportArtifact[] }
  | { status: "unauthorized"; summary: null; exports: [] }
  | { status: "unavailable"; summary: null; exports: [] };

export async function getReviewReport(
  accessToken: string,
  organizationId: string,
  reviewId: string,
): Promise<ReviewReportResult> {
  const apiBaseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  const headers = {
    Accept: "application/json",
    Authorization: `Bearer ${accessToken}`,
    "X-Organization-ID": organizationId,
  };
  try {
    const [summaryResponse, exportsResponse] = await Promise.all([
      fetch(`${apiBaseUrl}/api/v1/prisma/reviews/${reviewId}/summary`, {
        cache: "no-store",
        headers,
      }),
      fetch(`${apiBaseUrl}/api/v1/exports/reviews/${reviewId}`, {
        cache: "no-store",
        headers,
      }),
    ]);
    if (
      [summaryResponse.status, exportsResponse.status].some(
        (responseStatus) => responseStatus === 401 || responseStatus === 403,
      )
    ) {
      return { status: "unauthorized", summary: null, exports: [] };
    }
    if (!summaryResponse.ok || !exportsResponse.ok) {
      return { status: "unavailable", summary: null, exports: [] };
    }
    return {
      status: "ready",
      summary: (await summaryResponse.json()) as PrismaSummary,
      exports: (await exportsResponse.json()) as ExportArtifact[],
    };
  } catch {
    return { status: "unavailable", summary: null, exports: [] };
  }
}

export type SearchStrategyVersion = {
  id: string;
  version: number;
  content: { name: string };
  content_hash: string;
};

export type IdentificationSource = {
  id: string;
  source_key: string;
  display_name: string;
  classification: string;
  provider_name: string;
  platform_name: string | null;
};

export type SearchExecution = {
  id: string;
  source: IdentificationSource;
  search_strategy_version_id: string | null;
  search_translation_id: string | null;
  method: string;
  exact_query: string | null;
  filters: Record<string, string>;
  executed_at: string;
  software_version: string | null;
  status: string;
  provider_result_count: number | null;
  imported_record_count: number;
  events: Array<{
    sequence: number;
    status: string;
    provider_result_count: number | null;
    note: string | null;
    occurred_at: string;
  }>;
};

export type CitationImport = {
  id: string;
  source_format: string;
  source_name: string;
  content_hash: string;
  record_count: number;
};

export type SearchDocumentationResult =
  | {
      status: "ready";
      strategies: SearchStrategyVersion[];
      sources: IdentificationSource[];
      executions: SearchExecution[];
      imports: CitationImport[];
    }
  | {
      status: "unauthorized" | "unavailable";
      strategies: [];
      sources: [];
      executions: [];
      imports: [];
    };

export async function getSearchDocumentation(
  accessToken: string,
  organizationId: string,
  reviewId: string,
): Promise<SearchDocumentationResult> {
  const apiBaseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  const headers = {
    Accept: "application/json",
    Authorization: `Bearer ${accessToken}`,
    "X-Organization-ID": organizationId,
  };
  const paths = [
    `/api/v1/search-strategies/reviews/${reviewId}/versions`,
    `/api/v1/search-executions/reviews/${reviewId}/sources`,
    `/api/v1/search-executions/reviews/${reviewId}`,
    `/api/v1/citations/reviews/${reviewId}/imports`,
  ];
  try {
    const responses = await Promise.all(
      paths.map((path) => fetch(`${apiBaseUrl}${path}`, { cache: "no-store", headers })),
    );
    if (responses.some((response) => response.status === 401 || response.status === 403)) {
      return { status: "unauthorized", strategies: [], sources: [], executions: [], imports: [] };
    }
    if (responses.some((response) => !response.ok)) {
      return { status: "unavailable", strategies: [], sources: [], executions: [], imports: [] };
    }
    const [strategies, sources, executions, imports] = await Promise.all(
      responses.map((response) => response.json()),
    );
    return {
      status: "ready",
      strategies: strategies as SearchStrategyVersion[],
      sources: sources as IdentificationSource[],
      executions: executions as SearchExecution[],
      imports: imports as CitationImport[],
    };
  } catch {
    return { status: "unavailable", strategies: [], sources: [], executions: [], imports: [] };
  }
}

export type RiskOfBiasInstrumentVersion = {
  id: string;
  instrument_id: string;
  version: number;
  definition: {
    name: string;
    applicable_study_designs: string[];
    answer_choices: Array<{ value: string; label: string }>;
    domain_judgment_choices: Array<{ value: string; label: string }>;
    overall_judgment_choices: Array<{ value: string; label: string }>;
    domains: Array<{
      key: string;
      label: string;
      questions: Array<{ key: string; text: string; allowed_answers: string[] }>;
    }>;
  };
  content_hash: string;
  decision: "APPROVED" | "REJECTED" | null;
};

export type RiskOfBiasInstrument = {
  id: string;
  key: string;
  name: string;
  description: string | null;
  versions: RiskOfBiasInstrumentVersion[];
};

export type RiskOfBiasAssessment = {
  id: string;
  study_id: string;
  instrument_version_id: string;
  assessor_user_id: string;
  round_number: number;
  revision: number;
  status: "IN_PROGRESS" | "SUBMITTED";
  overall_final_judgment: string | null;
  answers: Array<{ question_key: string; answer: string }>;
  domain_judgments: Array<{
    domain_key: string;
    suggested_judgment: string | null;
    final_judgment: string;
  }>;
};

export type RiskOfBiasComparison = {
  id: string;
  study_id: string;
  assessment_a_id: string;
  assessment_b_id: string;
  status: "AGREEMENT" | "CONFLICT" | "ADJUDICATED";
  differences: Array<{ scope: string; key: string; value_a: unknown; value_b: unknown }>;
  adjudication_reason: string | null;
};

export type StudySummary = {
  id: string;
  study_key: string;
  label: string | null;
  study_design: string | null;
};

export type RiskOfBiasWorkspaceResult =
  | {
      status: "ready";
      instruments: RiskOfBiasInstrument[];
      studies: StudySummary[];
      assessments: RiskOfBiasAssessment[];
      comparisons: RiskOfBiasComparison[];
    }
  | {
      status: "unauthorized" | "unavailable";
      instruments: [];
      studies: [];
      assessments: [];
      comparisons: [];
    };

export async function getRiskOfBiasWorkspace(
  accessToken: string,
  organizationId: string,
  reviewId: string,
): Promise<RiskOfBiasWorkspaceResult> {
  const apiBaseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  const headers = {
    Accept: "application/json",
    Authorization: `Bearer ${accessToken}`,
    "X-Organization-ID": organizationId,
  };
  const paths = [
    `/api/v1/risk-of-bias/reviews/${reviewId}/instruments`,
    `/api/v1/studies/reviews/${reviewId}`,
    `/api/v1/risk-of-bias/reviews/${reviewId}/assessments`,
    `/api/v1/risk-of-bias/reviews/${reviewId}/comparisons`,
  ];
  try {
    const responses = await Promise.all(
      paths.map((path) => fetch(`${apiBaseUrl}${path}`, { cache: "no-store", headers })),
    );
    if (responses.some((response) => response.status === 401 || response.status === 403)) {
      return {
        status: "unauthorized",
        instruments: [],
        studies: [],
        assessments: [],
        comparisons: [],
      };
    }
    if (responses.some((response) => !response.ok)) {
      return {
        status: "unavailable",
        instruments: [],
        studies: [],
        assessments: [],
        comparisons: [],
      };
    }
    const [instruments, studies, assessments, comparisons] = await Promise.all(
      responses.map((response) => response.json()),
    );
    return {
      status: "ready",
      instruments: instruments as RiskOfBiasInstrument[],
      studies: studies as StudySummary[],
      assessments: assessments as RiskOfBiasAssessment[],
      comparisons: comparisons as RiskOfBiasComparison[],
    };
  } catch {
    return {
      status: "unavailable",
      instruments: [],
      studies: [],
      assessments: [],
      comparisons: [],
    };
  }
}

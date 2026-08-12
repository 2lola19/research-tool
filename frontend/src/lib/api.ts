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

export type OutcomeVersion = {
  id: string;
  outcome_id: string;
  version: number;
  definition: {
    name: string;
    description: string | null;
    outcome_type: string;
    directionality: string;
    role: string;
    compatible_effect_measures: string[];
    expected_timepoint_window_ids: string[];
  };
  content_hash: string;
  protocol_version_id: string | null;
};

export type OutcomeDefinition = {
  id: string;
  key: string;
  versions: OutcomeVersion[];
};

export type OutcomeConfiguration = {
  timepoint_windows: Array<{
    id: string;
    key: string;
    label: string;
    anchor: string;
    minimum_days: string | null;
    maximum_days: string | null;
    rule_version: string;
  }>;
  units: Array<{
    id: string;
    key: string;
    label: string;
    dimension: string;
    context_key: string;
    rule_version: string;
  }>;
  measurement_scales: Array<{
    id: string;
    key: string;
    name: string;
    directionality: string;
  }>;
};

export type OutcomeMapping = {
  id: string;
  study_id: string;
  extraction_value_id: string;
  outcome_version_id: string;
  method: string;
  reported_value: string | null;
  reported_unit: string | null;
  normalized_value: string | null;
  normalized_time_days: string | null;
  timepoint_window_id: string | null;
  extraction_verified: boolean;
};

export type EffectEstimate = {
  id: string;
  study_id: string;
  outcome_version_id: string;
  effect_measure: string;
  origin: string;
  estimate: string | null;
  standard_error: string | null;
  variance: string | null;
  variance_scale: string;
  adjustment: string;
  analysis_population: string;
  components: Record<string, string>;
  source_mapping_ids: string[];
  calculation_version: string | null;
  zero_event_pattern: string;
};

export type SynthesisCandidate = {
  id: string;
  outcome_version_id: string;
  effect_measure: string;
  timepoint_window_id: string | null;
  population_label: string | null;
  estimate_ids: string[];
};

export type ReadinessSnapshot = {
  id: string;
  candidate_set_id: string;
  algorithm_version: string;
  status: string;
  blockers: Array<{ code: string; estimate_id?: string; study_id?: string }>;
};

export type OutcomeWorkspaceResult =
  | {
      status: "ready";
      outcomes: OutcomeDefinition[];
      configuration: OutcomeConfiguration;
      mappings: OutcomeMapping[];
      estimates: EffectEstimate[];
      candidates: SynthesisCandidate[];
      readiness: ReadinessSnapshot[];
      studies: StudySummary[];
    }
  | {
      status: "unauthorized" | "unavailable";
      outcomes: [];
      configuration: OutcomeConfiguration;
      mappings: [];
      estimates: [];
      candidates: [];
      readiness: [];
      studies: [];
    };

const emptyOutcomeConfiguration: OutcomeConfiguration = {
  timepoint_windows: [],
  units: [],
  measurement_scales: [],
};

export async function getOutcomeWorkspace(
  accessToken: string,
  organizationId: string,
  reviewId: string,
): Promise<OutcomeWorkspaceResult> {
  const apiBaseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  const headers = {
    Accept: "application/json",
    Authorization: `Bearer ${accessToken}`,
    "X-Organization-ID": organizationId,
  };
  const paths = [
    `/api/v1/outcomes/reviews/${reviewId}`,
    `/api/v1/outcomes/reviews/${reviewId}/configuration`,
    `/api/v1/outcomes/reviews/${reviewId}/mappings`,
    `/api/v1/outcomes/reviews/${reviewId}/effect-estimates`,
    `/api/v1/outcomes/reviews/${reviewId}/candidate-sets`,
    `/api/v1/studies/reviews/${reviewId}`,
  ];
  try {
    const responses = await Promise.all(
      paths.map((path) => fetch(`${apiBaseUrl}${path}`, { cache: "no-store", headers })),
    );
    if (responses.some((response) => response.status === 401 || response.status === 403)) {
      return {
        status: "unauthorized",
        outcomes: [],
        configuration: emptyOutcomeConfiguration,
        mappings: [],
        estimates: [],
        candidates: [],
        readiness: [],
        studies: [],
      };
    }
    if (responses.some((response) => !response.ok)) {
      return {
        status: "unavailable",
        outcomes: [],
        configuration: emptyOutcomeConfiguration,
        mappings: [],
        estimates: [],
        candidates: [],
        readiness: [],
        studies: [],
      };
    }
    const [outcomes, configuration, mappings, estimates, candidatePayload, studies] =
      await Promise.all(responses.map((response) => response.json()));
    const candidateData = candidatePayload as {
      candidate_sets: SynthesisCandidate[];
      readiness_snapshots: ReadinessSnapshot[];
    };
    return {
      status: "ready",
      outcomes: outcomes as OutcomeDefinition[],
      configuration: configuration as OutcomeConfiguration,
      mappings: mappings as OutcomeMapping[],
      estimates: estimates as EffectEstimate[],
      candidates: candidateData.candidate_sets,
      readiness: candidateData.readiness_snapshots,
      studies: studies as StudySummary[],
    };
  } catch {
    return {
      status: "unavailable",
      outcomes: [],
      configuration: emptyOutcomeConfiguration,
      mappings: [],
      estimates: [],
      candidates: [],
      readiness: [],
      studies: [],
    };
  }
}

export type AnalysisSpecificationVersion = {
  id: string;
  version: number;
  content_hash: string;
  definition: {
    outcome_version_id: string;
    timepoint_window_id: string | null;
    synthesis_population: string;
    intervention: string;
    comparator: string;
    effect_measure: string;
    model: string;
    heterogeneity_estimator: string;
    confidence_level: string;
    transformation: string;
    zero_event_policy: string;
    adjustment_policy: string;
    analysis_population: string;
    minimum_studies: number;
    prediction_interval: boolean;
  };
};

export type AnalysisSpecification = {
  id: string;
  key: string;
  versions: AnalysisSpecificationVersion[];
};

export type StatisticalAnalysisSet = {
  id: string;
  specification_version_id: string;
  candidate_set_id: string;
  included_estimate_ids: string[];
  excluded_estimates: Array<{ estimate_id: string; code: string }>;
  input_hash: string;
};

export type MetaAnalysisRun = {
  id: string;
  specification_version_id: string;
  analysis_set_id: string;
  status: "PLANNED" | "RUNNING" | "COMPLETED" | "FAILED";
  algorithm_name: string;
  algorithm_version: string;
  provider: string;
  input_hash: string;
  result_hash: string | null;
  result: {
    presentation_estimate: string;
    presentation_ci_lower: string;
    presentation_ci_upper: string;
    number_of_studies: number;
    model: string;
    estimator: string;
    heterogeneity: {
      q: string;
      degrees_of_freedom: number;
      q_p_value: string;
      tau_squared: string;
      i_squared_percent: string;
    };
    weights: Array<{
      study_id: string;
      estimate_id: string;
      analysis_estimate: string;
      normalized_weight_percent: string;
    }>;
    sensitivity: Array<{
      omitted_study_id: string;
      presentation_estimate: string;
      presentation_ci_lower: string;
      presentation_ci_upper: string;
    }>;
  } | null;
  diagnostics: Array<{ code: string; level: string; message: string }>;
  failure_reason: string | null;
  stale: boolean;
};

export type AnalysisArtifact = {
  id: string;
  run_id: string;
  artifact_type: string;
  renderer_version: string;
  filename: string;
  sha256: string;
  byte_size: number;
};

export type AnalysisWorkspaceResult =
  | {
      status: "ready";
      specifications: AnalysisSpecification[];
      analysisSets: StatisticalAnalysisSet[];
      runs: MetaAnalysisRun[];
      artifacts: AnalysisArtifact[];
    }
  | {
      status: "unauthorized" | "unavailable";
      specifications: [];
      analysisSets: [];
      runs: [];
      artifacts: [];
    };

export async function getAnalysisWorkspace(
  accessToken: string,
  organizationId: string,
  reviewId: string,
): Promise<AnalysisWorkspaceResult> {
  const apiBaseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  try {
    const response = await fetch(`${apiBaseUrl}/api/v1/analysis/reviews/${reviewId}`, {
      cache: "no-store",
      headers: {
        Accept: "application/json",
        Authorization: `Bearer ${accessToken}`,
        "X-Organization-ID": organizationId,
      },
    });
    if (response.status === 401 || response.status === 403) {
      return { status: "unauthorized", specifications: [], analysisSets: [], runs: [], artifacts: [] };
    }
    if (!response.ok) {
      return { status: "unavailable", specifications: [], analysisSets: [], runs: [], artifacts: [] };
    }
    const payload = (await response.json()) as {
      specifications: AnalysisSpecification[];
      analysis_sets: StatisticalAnalysisSet[];
      runs: MetaAnalysisRun[];
      artifacts: AnalysisArtifact[];
    };
    return {
      status: "ready",
      specifications: payload.specifications,
      analysisSets: payload.analysis_sets,
      runs: payload.runs,
      artifacts: payload.artifacts,
    };
  } catch {
    return { status: "unavailable", specifications: [], analysisSets: [], runs: [], artifacts: [] };
  }
}

export type CertaintyFrameworkVersion = {
  id: string;
  framework_id: string;
  version: number;
  definition: {
    name: string;
    version_label: string;
    starting_rules: Record<string, string>;
    domains: Array<{
      key: string;
      label: string;
      direction: "DOWNGRADE" | "UPGRADE";
      choices: Array<{ value: string; label: string; magnitude: number }>;
    }>;
  };
  content_hash: string;
};

export type CertaintyFramework = {
  id: string;
  key: string;
  name: string;
  description: string | null;
  versions: CertaintyFrameworkVersion[];
};

export type CertaintyAssessment = {
  id: string;
  outcome_version_id: string;
  timepoint_window_id: string | null;
  analysis_specification_version_id: string | null;
  meta_analysis_run_id: string | null;
  framework_version_id: string;
  threshold_version_id: string | null;
  assessor_user_id: string;
  round_number: number;
  revision: number;
  supersedes_assessment_id: string | null;
  evidence_body_type: "RANDOMIZED" | "OBSERVATIONAL" | "MIXED" | "OTHER";
  evidence_body: Record<string, unknown>;
  starting_certainty: "HIGH" | "MODERATE" | "LOW" | "VERY_LOW";
  starting_rationale: string;
  status: "IN_PROGRESS" | "SUBMITTED";
  candidate_certainty: string | null;
  final_certainty: string | null;
  final_rationale: string | null;
  override_reason: string | null;
  evidence_hash: string | null;
  stale: boolean;
  domain_judgments: Array<{
    id: string;
    domain_key: string;
    direction: "DOWNGRADE" | "UPGRADE";
    magnitude: number;
    judgment: string;
    rationale: string;
    evidence_location_id: string | null;
    evidence: Record<string, unknown>;
  }>;
};

export type CertaintyComparison = {
  id: string;
  outcome_version_id: string;
  framework_version_id: string;
  round_number: number;
  assessment_a_id: string;
  assessment_b_id: string;
  status: "AGREEMENT" | "CONFLICT" | "ADJUDICATED";
  differences: Array<Record<string, unknown>>;
  adjudicated_snapshot: Record<string, unknown> | null;
  adjudication_reason: string | null;
};

export type SummaryOfFindingsSnapshot = {
  id: string;
  assessment_id: string;
  model_version: string;
  row: Record<string, unknown>;
  content_hash: string;
  created_at: string;
};

export type CertaintyWorkspaceResult =
  | {
      status: "ready";
      frameworks: CertaintyFramework[];
      thresholdVersions: Array<Record<string, unknown>>;
      assessments: CertaintyAssessment[];
      comparisons: CertaintyComparison[];
      comparisonCandidates: Array<{ id: string; outcome_version_id: string; framework_version_id: string; round_number: number; assessor_user_id: string }>;
      summaryOfFindings: SummaryOfFindingsSnapshot[];
    }
  | {
      status: "unauthorized" | "unavailable";
      frameworks: CertaintyFramework[];
      thresholdVersions: Array<Record<string, unknown>>;
      assessments: CertaintyAssessment[];
      comparisons: CertaintyComparison[];
      comparisonCandidates: Array<{
        id: string;
        outcome_version_id: string;
        framework_version_id: string;
        round_number: number;
        assessor_user_id: string;
      }>;
      summaryOfFindings: SummaryOfFindingsSnapshot[];
    };

export async function getCertaintyWorkspace(
  accessToken: string,
  organizationId: string,
  reviewId: string,
): Promise<CertaintyWorkspaceResult> {
  const empty = {
    frameworks: [],
    thresholdVersions: [],
    assessments: [],
    comparisons: [],
    comparisonCandidates: [],
    summaryOfFindings: [],
  };
  const apiBaseUrl = process.env.API_BASE_URL ?? "http://localhost:8000";
  try {
    const response = await fetch(
      apiBaseUrl + "/api/v1/certainty/reviews/" + reviewId,
      {
        cache: "no-store",
        headers: {
          Accept: "application/json",
          Authorization: "Bearer " + accessToken,
          "X-Organization-ID": organizationId,
        },
      },
    );
    if (response.status === 401 || response.status === 403) {
      return { status: "unauthorized", ...empty };
    }
    if (!response.ok) {
      return { status: "unavailable", ...empty };
    }
    const payload = (await response.json()) as {
      frameworks: CertaintyFramework[];
      threshold_versions: Array<Record<string, unknown>>;
      assessments: CertaintyAssessment[];
      comparisons: CertaintyComparison[];
      comparison_candidates: Array<{ id: string; outcome_version_id: string; framework_version_id: string; round_number: number; assessor_user_id: string }>;
      summary_of_findings: SummaryOfFindingsSnapshot[];
    };
    return {
      status: "ready",
      frameworks: payload.frameworks,
      thresholdVersions: payload.threshold_versions,
      assessments: payload.assessments,
      comparisons: payload.comparisons,
      comparisonCandidates: payload.comparison_candidates,
      summaryOfFindings: payload.summary_of_findings,
    };
  } catch {
    return { status: "unavailable", ...empty };
  }
}
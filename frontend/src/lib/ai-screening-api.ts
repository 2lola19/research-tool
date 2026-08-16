export type AIScreeningPolicy = {
  id: string;
  review_id: string;
  version: number;
  mode: "OFF" | "BLINDED_AI" | "ASSISTED";
  maximum_batch_size: number;
  created_by_user_id: string;
  created_at: string;
};

export type AIScreeningSuggestion = {
  assignment_id: string;
  article_id: string;
  proposal_id: string;
  ai_run_id: string;
  mode: "OFF" | "BLINDED_AI" | "ASSISTED";
  is_revealed: boolean;
  suggestion: "INCLUDE" | "EXCLUDE" | "MAYBE" | "ABSTAIN" | null;
  structured_value: Record<string, unknown> | null;
  protocol_version_id: string;
  citation_content_hash: string;
  accessed: boolean;
};

export type ScreeningQueueItem = {
  assignment_id: string;
  article_id: string;
  title: string;
  abstract: string | null;
  own_decision: "INCLUDE" | "EXCLUDE" | null;
  outcome: "INCLUDE" | "EXCLUDE" | "CONFLICT" | null;
};

export type ScreeningEvaluationDataset = {
  id: string;
  review_id: string;
  logical_key: string;
  version: number;
  protocol_version_id: string;
  name: string;
  reference_standard: string;
  content_hash: string;
  created_by_user_id: string;
  created_at: string;
};

export type ScreeningEvaluation = {
  id: string;
  dataset_id: string;
  evaluation_policy: string;
  metric_version: string;
  metrics: Record<string, unknown>;
  calibration: Array<Record<string, unknown>>;
  threshold_simulation: Array<Record<string, unknown>>;
  high_risk_disagreements: Array<Record<string, unknown>>;
  content_hash: string;
  created_at: string;
};

export type AIScreeningWorkspace = {
  status: "ready" | "unauthorized" | "unavailable";
  policy: AIScreeningPolicy | null;
  queue: ScreeningQueueItem[];
  datasets: ScreeningEvaluationDataset[];
  evaluations: ScreeningEvaluation[];
};

const empty: AIScreeningWorkspace = {
  status: "unavailable",
  policy: null,
  queue: [],
  datasets: [],
  evaluations: [],
};

function headers(accessToken: string, organizationId: string): HeadersInit {
  return {
    Accept: "application/json",
    Authorization: `Bearer ${accessToken}`,
    "X-Organization-ID": organizationId,
  };
}

export async function getAIScreeningWorkspace(
  accessToken: string,
  organizationId: string,
  reviewId: string,
  roundId?: string,
): Promise<AIScreeningWorkspace> {
  const base = process.env.API_BASE_URL ?? "http://localhost:8000";
  const requests = [
    fetch(`${base}/api/v1/ai/screening/reviews/${reviewId}/policy`, {
      cache: "no-store",
      headers: headers(accessToken, organizationId),
    }),
    fetch(`${base}/api/v1/ai/screening/reviews/${reviewId}/evaluation-datasets`, {
      cache: "no-store",
      headers: headers(accessToken, organizationId),
    }),
    fetch(`${base}/api/v1/ai/screening/reviews/${reviewId}/evaluations`, {
      cache: "no-store",
      headers: headers(accessToken, organizationId),
    }),
  ];
  if (roundId) {
    requests.push(
      fetch(`${base}/api/v1/screening/rounds/${roundId}/queue`, {
        cache: "no-store",
        headers: headers(accessToken, organizationId),
      }),
    );
  }
  try {
    const responses = await Promise.all(requests);
    if (responses.some((response) => response.status === 401 || response.status === 403)) {
      return { ...empty, status: "unauthorized" };
    }
    if (responses.some((response) => !response.ok)) return empty;
    const policy = (await responses[0].json()) as AIScreeningPolicy | null;
    const datasets = (await responses[1].json()) as ScreeningEvaluationDataset[];
    const evaluations = (await responses[2].json()) as ScreeningEvaluation[];
    const queue = roundId
      ? ((await responses[3].json()) as ScreeningQueueItem[])
      : [];
    return { status: "ready", policy, queue, datasets, evaluations };
  } catch {
    return empty;
  }
}

export async function getAIScreeningSuggestion(
  accessToken: string,
  organizationId: string,
  reviewId: string,
  assignmentId: string,
): Promise<AIScreeningSuggestion | null> {
  try {
    const response = await fetch(
      `${process.env.API_BASE_URL ?? "http://localhost:8000"}/api/v1/ai/screening/reviews/${reviewId}/assignments/${assignmentId}/suggestion`,
      { cache: "no-store", headers: headers(accessToken, organizationId) },
    );
    return response.ok ? ((await response.json()) as AIScreeningSuggestion) : null;
  } catch {
    return null;
  }
}

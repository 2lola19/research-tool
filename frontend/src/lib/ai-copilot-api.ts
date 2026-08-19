export type AICopilotCitation = {
  citation_id: string;
  source_type: string;
  source_id: string;
  label: string;
  locator: Record<string, string | number>;
};

export type AICopilotQuery = {
  id: string;
  review_id: string;
  task_key: string;
  query: string;
  context_hash: string;
  citations: AICopilotCitation[];
  ai_run_id: string | null;
  proposal_id: string | null;
  answer: {
    answer: string;
    citations: Array<{ citation_id: string; claim: string }>;
    abstention: string | null;
    uncertainty_reason: string | null;
    model_reported_confidence: number | null;
  } | null;
  validation_results: Record<string, unknown>;
  status: string;
  failure_reason: string | null;
  stale: boolean;
  stale_reasons: string[];
  created_at: string;
};

export type AICopilotWorkspace = {
  status: "ready" | "unauthorized" | "unavailable";
  tasks: Array<{ task_key: string; label: string; description: string; read_only: boolean }>;
  policy: {
    id: string;
    version: number;
    maximum_query_characters: number;
    maximum_context_items: number;
  } | null;
  queries: AICopilotQuery[];
};

const empty: AICopilotWorkspace = {
  status: "unavailable",
  tasks: [],
  policy: null,
  queries: [],
};

export async function getAICopilotWorkspace(
  accessToken: string,
  organizationId: string,
  reviewId: string,
): Promise<AICopilotWorkspace> {
  const base = process.env.API_BASE_URL ?? "http://localhost:8000";
  const headers = {
    Accept: "application/json",
    Authorization: `Bearer ${accessToken}`,
    "X-Organization-ID": organizationId,
  };
  try {
    const [tasks, policy, queries] = await Promise.all([
      fetch(`${base}/api/v1/ai/copilot/tasks`, { cache: "no-store", headers }),
      fetch(`${base}/api/v1/ai/copilot/reviews/${reviewId}/policy`, { cache: "no-store", headers }),
      fetch(`${base}/api/v1/ai/copilot/reviews/${reviewId}/queries`, { cache: "no-store", headers }),
    ]);
    if ([tasks, queries].some((response) => response.status === 401 || response.status === 403)) {
      return { ...empty, status: "unauthorized" };
    }
    if ([tasks, queries].some((response) => !response.ok)) return empty;
    return {
      status: "ready",
      tasks: await tasks.json(),
      policy: policy.ok ? await policy.json() : null,
      queries: await queries.json(),
    };
  } catch {
    return empty;
  }
}

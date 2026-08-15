export type AIRun = {
  id: string;
  task_type: string;
  state: string;
  model_version_id: string;
  prompt_version_id: string;
  input_hash: string;
  identical_prior_run_id: string | null;
  created_at: string;
  completed_at: string | null;
};

export type AIWorkspace = {
  status: "ready" | "unauthorized" | "unavailable";
  registry: {
    providers: Array<{ key: string; network_required: boolean }>;
    models: Array<{ id: string; display_name: string; model_identifier: string; active: boolean }>;
    prompts: Array<{ id: string; prompt_key: string; version: number; content_hash: string }>;
    tasks: Array<{ task_type: string; risk: string; human_review_required: boolean }>;
  };
  runs: AIRun[];
  usage: Record<string, number | string>;
};

const empty: AIWorkspace = {
  status: "unavailable",
  registry: { providers: [], models: [], prompts: [], tasks: [] },
  runs: [],
  usage: {},
};

export async function getAIWorkspace(
  accessToken: string,
  organizationId: string,
  reviewId: string,
): Promise<AIWorkspace> {
  const base = process.env.API_BASE_URL ?? "http://localhost:8000";
  const headers = {
    Accept: "application/json",
    Authorization: `Bearer ${accessToken}`,
    "X-Organization-ID": organizationId,
  };
  try {
    const [registry, runs, usage] = await Promise.all([
      fetch(`${base}/api/v1/ai/registry`, { cache: "no-store", headers }),
      fetch(`${base}/api/v1/ai/reviews/${reviewId}/runs`, { cache: "no-store", headers }),
      fetch(`${base}/api/v1/ai/reviews/${reviewId}/usage`, { cache: "no-store", headers }),
    ]);
    if ([registry, runs, usage].some((response) => response.status === 401 || response.status === 403)) {
      return { ...empty, status: "unauthorized" };
    }
    if ([registry, runs, usage].some((response) => !response.ok)) return empty;
    return {
      status: "ready",
      registry: await registry.json(),
      runs: await runs.json(),
      usage: await usage.json(),
    };
  } catch {
    return empty;
  }
}

export async function getAIProposal(
  accessToken: string,
  organizationId: string,
  reviewId: string,
  proposalId: string,
): Promise<Record<string, unknown> | null> {
  try {
    const response = await fetch(
      `${process.env.API_BASE_URL ?? "http://localhost:8000"}/api/v1/ai/reviews/${reviewId}/proposals/${proposalId}`,
      {
        cache: "no-store",
        headers: {
          Accept: "application/json",
          Authorization: `Bearer ${accessToken}`,
          "X-Organization-ID": organizationId,
        },
      },
    );
    return response.ok ? ((await response.json()) as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

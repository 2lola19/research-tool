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

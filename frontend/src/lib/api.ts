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

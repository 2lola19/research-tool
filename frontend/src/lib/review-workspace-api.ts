import type { PrismaSummary, ReviewProject } from "./api";

export type WorkspaceSectionStatus = "ready" | "forbidden" | "unavailable" | "not_requested";

export type WorkspaceSection<T> = {
  status: WorkspaceSectionStatus;
  data: T;
};

export type ReviewParticipant = {
  user_id: string;
  email: string;
  display_name: string;
  organization_role: string;
};

export type ScreeningRound = {
  id: string;
  review_id: string;
  name: string;
  stage: "TITLE_ABSTRACT" | "FULL_TEXT";
  sequence: number;
  required_decisions: number;
  blinded: boolean;
  state: "OPEN" | "CLOSED";
};

export type ScreeningQueueItem = {
  assignment_id: string;
  article_id: string;
  title: string;
  abstract: string | null;
  own_decision: "INCLUDE" | "EXCLUDE" | null;
  outcome: "INCLUDE" | "EXCLUDE" | "CONFLICT" | null;
};

export type ScreeningOutcome = {
  id: string;
  article_id: string;
  outcome: "INCLUDE" | "EXCLUDE" | "CONFLICT";
  adjudication: "INCLUDE" | "EXCLUDE" | null;
};

export type WorkflowAttempt = {
  id: string;
  job_id: string;
  review_id: string;
  attempt_number: number;
  worker_id: string;
  state: "CLAIMED" | "RUNNING" | "COMPLETED" | "FAILED" | "EXPIRED";
  claimed_at: string;
  lease_expires_at: string;
  deadline_at: string;
  heartbeat_at: string;
  started_at: string;
  finished_at: string | null;
  result_snapshot: Record<string, unknown> | null;
  failure_code: string | null;
  failure_message: string | null;
};

export type WorkflowStepCheckpoint = {
  id: string;
  workflow_run_id: string;
  job_id: string | null;
  review_id: string;
  step_key: string;
  step_order: number;
  definition_hash: string | null;
  state:
    | "PENDING"
    | "QUEUED"
    | "RUNNING"
    | "AWAITING_HUMAN"
    | "COMPLETED"
    | "FAILED"
    | "DEAD_LETTERED"
    | "CANCELLED";
  checkpoint_version: number;
  output_digest: string | null;
  failure_class: string | null;
  checkpointed_at: string;
  updated_at: string;
};

export type WorkflowReconciliation = {
  review_id: string;
  generated_at: string;
  healthy: boolean;
  issues: Array<{
    code: string;
    severity: "WARNING" | "ERROR" | string;
    job_id: string;
    attempt_id: string | null;
    message: string;
  }>;
};

export type ProvenanceRecord = {
  id: string;
  review_id: string;
  subject_type: string;
  subject_id: string;
  source_type: string | null;
  source_id: string | null;
  source_locator: Record<string, unknown>;
  method_name: string;
  method_version: string;
  actor_kind: string;
  actor_user_id: string | null;
  ai_run_id: string | null;
  confidence: number | null;
  verification_state: string;
};

export type ReviewOperationsWorkspace = {
  review: ReviewProject;
  fetched_at: string;
  selected_round_id: string | null;
  members: WorkspaceSection<ReviewParticipant[]>;
  rounds: WorkspaceSection<ScreeningRound[]>;
  queue: WorkspaceSection<ScreeningQueueItem[]>;
  outcomes: WorkspaceSection<ScreeningOutcome[]>;
  prisma: WorkspaceSection<PrismaSummary | null>;
  attempts: WorkspaceSection<WorkflowAttempt[]>;
  checkpoints: WorkspaceSection<WorkflowStepCheckpoint[]>;
  reconciliation: WorkspaceSection<WorkflowReconciliation | null>;
  provenance: WorkspaceSection<ProvenanceRecord[]>;
};

export type ReviewOperationsResult =
  | { status: "ready"; workspace: ReviewOperationsWorkspace }
  | { status: "unauthorized" }
  | { status: "unavailable" };

const baseUrl = () => process.env.API_BASE_URL ?? "http://localhost:8000";

function requestHeaders(accessToken: string, organizationId: string): HeadersInit {
  return {
    Accept: "application/json",
    Authorization: `Bearer ${accessToken}`,
    "X-Organization-ID": organizationId,
  };
}

async function fetchSection<T>(
  path: string,
  headers: HeadersInit,
): Promise<{ status: WorkspaceSectionStatus | "unauthorized"; data: T }> {
  try {
    const response = await fetch(`${baseUrl()}${path}`, {
      cache: "no-store",
      headers,
    });
    if (response.status === 401) return { status: "unauthorized", data: null as T };
    if (response.status === 403 || response.status === 404) {
      return { status: "forbidden", data: null as T };
    }
    if (!response.ok) return { status: "unavailable", data: null as T };
    return { status: "ready", data: (await response.json()) as T };
  } catch {
    return { status: "unavailable", data: null as T };
  }
}

function notRequested<T>(): WorkspaceSection<T> {
  return { status: "not_requested", data: null as T };
}

function sectionStatus(status: WorkspaceSectionStatus | "unauthorized"): WorkspaceSectionStatus {
  return status === "unauthorized" ? "unavailable" : status;
}

export async function getReviewOperationsWorkspace(
  accessToken: string,
  organizationId: string,
  reviewId: string,
  roundId?: string,
): Promise<ReviewOperationsResult> {
  const headers = requestHeaders(accessToken, organizationId);
  const [review, members, rounds, prisma, attempts, checkpoints, reconciliation, provenance] =
    await Promise.all([
      fetchSection<ReviewProject>(`/api/v1/reviews/${reviewId}`, headers),
      fetchSection<ReviewParticipant[]>(`/api/v1/reviews/${reviewId}/memberships`, headers),
      fetchSection<ScreeningRound[]>(`/api/v1/screening/reviews/${reviewId}/rounds`, headers),
      fetchSection<PrismaSummary>(`/api/v1/prisma/reviews/${reviewId}/summary`, headers),
      fetchSection<WorkflowAttempt[]>(
        `/api/v1/workflow/execution/reviews/${reviewId}/attempts`,
        headers,
      ),
      fetchSection<WorkflowStepCheckpoint[]>(
        `/api/v1/workflow/execution/reviews/${reviewId}/steps`,
        headers,
      ),
      fetchSection<WorkflowReconciliation>(
        `/api/v1/workflow/execution/reviews/${reviewId}/reconciliation`,
        headers,
      ),
      fetchSection<ProvenanceRecord[]>(
        `/api/v1/provenance/reviews/${reviewId}/records`,
        headers,
      ),
    ]);

  if ([review, members, rounds, prisma, attempts, checkpoints, reconciliation, provenance].some(
    (section) => section.status === "unauthorized",
  )) {
    return { status: "unauthorized" };
  }
  if (review.status !== "ready" || !review.data) return { status: "unavailable" };

  const [queue, outcomes] = roundId
    ? await Promise.all([
        fetchSection<ScreeningQueueItem[]>(
          `/api/v1/screening/rounds/${roundId}/queue`,
          headers,
        ),
        fetchSection<ScreeningOutcome[]>(
          `/api/v1/screening/rounds/${roundId}/outcomes`,
          headers,
        ),
      ])
    : [
        notRequested<ScreeningQueueItem[]>(),
        notRequested<ScreeningOutcome[]>(),
      ];

  if (queue.status === "unauthorized" || outcomes.status === "unauthorized") {
    return { status: "unauthorized" };
  }

  return {
    status: "ready",
    workspace: {
      review: review.data,
      fetched_at: new Date().toISOString(),
      selected_round_id: roundId ?? null,
      members: { status: sectionStatus(members.status), data: members.data ?? [] },
      rounds: { status: sectionStatus(rounds.status), data: rounds.data ?? [] },
      queue: { status: sectionStatus(queue.status), data: queue.data ?? [] },
      outcomes: { status: sectionStatus(outcomes.status), data: outcomes.data ?? [] },
      prisma: { status: sectionStatus(prisma.status), data: prisma.data ?? null },
      attempts: { status: sectionStatus(attempts.status), data: attempts.data ?? [] },
      checkpoints: { status: sectionStatus(checkpoints.status), data: checkpoints.data ?? [] },
      reconciliation: {
        status: sectionStatus(reconciliation.status),
        data: reconciliation.data ?? null,
      },
      provenance: { status: sectionStatus(provenance.status), data: provenance.data ?? [] },
    },
  };
}

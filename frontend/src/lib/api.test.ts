import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getAnalysisWorkspace,
  getBackendHealth,
  getOutcomeWorkspace,
  getReviewProjects,
  getReviewReport,
  getRiskOfBiasWorkspace,
  getSearchDocumentation,
} from "./api";

describe("getAnalysisWorkspace", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads immutable specifications, sets, runs, and artifacts", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          specifications: [{ id: "specification-1", versions: [{ id: "version-1" }] }],
          analysis_sets: [{ id: "set-1", input_hash: "input-hash" }],
          runs: [{ id: "run-1", status: "COMPLETED", stale: false }],
          artifacts: [{ id: "artifact-1", run_id: "run-1" }],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await getAnalysisWorkspace("signed-token", "organization-1", "review-1");

    expect(result.status).toBe("ready");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/analysis/reviews/review-1",
      expect.objectContaining({
        cache: "no-store",
        headers: expect.objectContaining({ "X-Organization-ID": "organization-1" }),
      }),
    );
    expect(result.analysisSets[0]?.id).toBe("set-1");
    expect(result.runs[0]?.stale).toBe(false);
  });
});

describe("getBackendHealth", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns structured backend readiness", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ status: "healthy", checks: { database: "up" } }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(getBackendHealth()).resolves.toEqual({
      status: "healthy",
      checks: { database: "up" },
    });
  });

  it("fails closed when the backend cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

    await expect(getBackendHealth()).resolves.toEqual({
      status: "unavailable",
      checks: { api: "down" },
    });
  });
});

describe("getOutcomeWorkspace", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads harmonization and readiness records in parallel", async () => {
    const payloads = [
      [{ id: "outcome-1", versions: [] }],
      { timepoint_windows: [], units: [], measurement_scales: [] },
      [{ id: "mapping-1", extraction_verified: true }],
      [{ id: "estimate-1", effect_measure: "RR" }],
      {
        candidate_sets: [{ id: "candidate-1" }],
        readiness_snapshots: [{ candidate_set_id: "candidate-1", status: "READY" }],
      },
      [{ id: "study-1", study_key: "S1" }],
    ];
    const fetchMock = vi.fn();
    for (const payload of payloads) {
      fetchMock.mockResolvedValueOnce(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }
    vi.stubGlobal("fetch", fetchMock);

    const result = await getOutcomeWorkspace("signed-token", "organization-1", "review-1");

    expect(result.status).toBe("ready");
    expect(fetchMock).toHaveBeenCalledTimes(6);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/outcomes/reviews/review-1/effect-estimates",
      expect.objectContaining({
        cache: "no-store",
        headers: expect.objectContaining({ "X-Organization-ID": "organization-1" }),
      }),
    );
  });
});

describe("getReviewProjects", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends both bearer identity and organization context", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([{ id: "review-1", title: "Evidence review" }]), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await getReviewProjects("signed-token", "organization-1");

    expect(result.status).toBe("ready");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/reviews",
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer signed-token",
          "X-Organization-ID": "organization-1",
        }),
      }),
    );
  });

  it("fails closed when tenant context is rejected", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 403 })));

    await expect(getReviewProjects("signed-token", "wrong-organization")).resolves.toEqual({
      status: "unauthorized",
      projects: [],
    });
  });
});

describe("getReviewReport", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads PRISMA readiness and export artifacts in parallel", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            counts: { records_screened: 12 },
            readiness: { ready_for_final: false, blockers: [] },
            source_references: {},
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify([{ id: "export-1", format: "CSV" }]), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const result = await getReviewReport("signed-token", "organization-1", "review-1");

    expect(result.status).toBe("ready");
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/prisma/reviews/review-1/summary",
      expect.objectContaining({ cache: "no-store" }),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/exports/reviews/review-1",
      expect.objectContaining({ cache: "no-store" }),
    );
  });
});

describe("getSearchDocumentation", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads strategies, sources, executions, and imports in parallel", async () => {
    const payloads = [
      [{ id: "strategy-1", version: 1, content: { name: "Core" } }],
      [{ id: "source-1", display_name: "PubMed" }],
      [{ id: "execution-1", status: "COMPLETED" }],
      [{ id: "import-1", record_count: 10 }],
    ];
    const fetchMock = vi.fn();
    for (const payload of payloads) {
      fetchMock.mockResolvedValueOnce(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }
    vi.stubGlobal("fetch", fetchMock);

    const result = await getSearchDocumentation("signed-token", "organization-1", "review-1");

    expect(result.status).toBe("ready");
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/search-executions/reviews/review-1",
      expect.objectContaining({
        cache: "no-store",
        headers: expect.objectContaining({ "X-Organization-ID": "organization-1" }),
      }),
    );
  });
});

describe("getRiskOfBiasWorkspace", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads instruments, Studies, blinded assessments, and comparisons in parallel", async () => {
    const payloads = [
      [{ id: "instrument-1", versions: [] }],
      [{ id: "study-1", study_design: "RANDOMIZED_CONTROLLED_TRIAL" }],
      [{ id: "assessment-1", status: "IN_PROGRESS" }],
      [{ id: "comparison-1", status: "CONFLICT" }],
    ];
    const fetchMock = vi.fn();
    for (const payload of payloads) {
      fetchMock.mockResolvedValueOnce(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }
    vi.stubGlobal("fetch", fetchMock);

    const result = await getRiskOfBiasWorkspace("signed-token", "organization-1", "review-1");

    expect(result.status).toBe("ready");
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/v1/risk-of-bias/reviews/review-1/assessments",
      expect.objectContaining({
        cache: "no-store",
        headers: expect.objectContaining({ "X-Organization-ID": "organization-1" }),
      }),
    );
  });
});

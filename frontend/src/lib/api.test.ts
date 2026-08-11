import { afterEach, describe, expect, it, vi } from "vitest";

import { getBackendHealth, getReviewProjects, getReviewReport } from "./api";

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

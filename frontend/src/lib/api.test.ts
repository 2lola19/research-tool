import { afterEach, describe, expect, it, vi } from "vitest";

import { getBackendHealth, getReviewProjects } from "./api";

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

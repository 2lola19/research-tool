import { afterEach, describe, expect, it, vi } from "vitest";

import { getBackendHealth } from "./api";

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


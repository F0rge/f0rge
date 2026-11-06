import { afterEach, describe, expect, it, vi } from "vitest";
import { setStaffTokenGetter, staffFetch } from "./staff-fetch";

describe("staff transport", () => {
  afterEach(() => {
    setStaffTokenGetter(null);
    vi.unstubAllGlobals();
  });
  it("resolves a fresh org token for every request, including uploads", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response("{}"));
    vi.stubGlobal("fetch", fetch);
    const getToken = vi
      .fn()
      .mockResolvedValueOnce("org-a")
      .mockResolvedValueOnce("org-b");
    setStaffTokenGetter(getToken);
    await staffFetch("/api/v1/skus");
    await staffFetch("/api/v1/skus/upload", {
      method: "POST",
      body: new FormData(),
    });
    expect(fetch.mock.calls[0][1].headers.get("Authorization")).toBe(
      "Bearer org-a",
    );
    expect(fetch.mock.calls[1][1].headers.get("Authorization")).toBe(
      "Bearer org-b",
    );
    expect(fetch.mock.calls[1][1].headers.has("Content-Type")).toBe(false);
  });
  it("keeps legacy cookies and excludes trade portal from staff auth", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response("{}"));
    vi.stubGlobal("fetch", fetch);
    await staffFetch("/api/v1/auth/me");
    const getToken = vi.fn().mockResolvedValue("staff");
    setStaffTokenGetter(getToken);
    await staffFetch("/api/v1/portal/orders");
    expect(getToken).not.toHaveBeenCalled();
    for (const call of fetch.mock.calls) {
      expect(call[1].credentials).toBe("include");
      expect(call[1].headers.has("Authorization")).toBe(false);
    }
  });
  it("fails closed on token retrieval error rather than silently falling back", async () => {
    const fetch = vi.fn();
    vi.stubGlobal("fetch", fetch);
    setStaffTokenGetter(async () => {
      throw new Error("expired");
    });
    await expect(staffFetch("/api/v1/skus")).rejects.toThrow("expired");
    expect(fetch).not.toHaveBeenCalled();
  });
});

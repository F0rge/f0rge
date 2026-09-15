import { afterEach, describe, expect, it, vi } from "vitest";

import { downloadApiFile } from "./download";

describe("downloadApiFile", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("rejects JSON error bodies instead of saving them as files", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "not allowed" }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(downloadApiFile("/api/v1/proformas/1/file", "x.pdf")).rejects.toMatchObject({
      status: 401,
      message: "not allowed",
    });
  });

  it("rejects HTML bodies even when the status is 200", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("<html>login</html>", {
          status: 200,
          headers: { "Content-Type": "text/html; charset=utf-8" },
        }),
      ),
    );

    await expect(downloadApiFile("/api/v1/proformas/1/file", "x.pdf")).rejects.toMatchObject({
      status: 200,
    });
  });
});

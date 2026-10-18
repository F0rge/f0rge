import { afterEach, describe, expect, it, vi } from "vitest";

import { formatHttpError, formatTransportError, listSkus } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("formatHttpError", () => {
  it("names a timeout and keeps domain messages", () => {
    expect(formatHttpError("GET /inventory", 499, "", "Request failed")).toBe(
      "GET /inventory timed out",
    );
    expect(formatHttpError("GET /skus", 504, "Gateway Timeout", "")).toBe("GET /skus timed out");
    expect(formatHttpError("GET /skus", 500, "", "Request failed")).toBe("GET /skus failed (500)");
    expect(formatHttpError("POST /till/sales", 409, "Conflict", "Customer is on hold")).toBe(
      "Customer is on hold",
    );
  });
});

describe("formatTransportError", () => {
  it("names aborted calls as timeouts", () => {
    expect(formatTransportError("GET /skus", new DOMException("aborted", "AbortError"))).toBe(
      "GET /skus timed out",
    );
    expect(formatTransportError("GET /skus", new TypeError("fetch failed"))).toBe(
      "GET /skus failed",
    );
  });
});

describe("listSkus errors", () => {
  it("reports a proxy timeout by call name", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("", { status: 499, statusText: "" })),
    );
    await expect(listSkus()).rejects.toThrow("GET /skus timed out");
  });
});

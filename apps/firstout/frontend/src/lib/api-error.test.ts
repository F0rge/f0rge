import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, createTillSale, formatHttpError, formatTransportError, listSkus } from "./api";
import { parseKitRequiresPick } from "./till-kit-pick";

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

describe("till kit block", () => {
  it("surfaces the blocking kit name from the sale error detail", async () => {
    const kitName = "Eva Headboard Grey w/ base 206*172cm";
    const message = `${kitName} (P36410/2) is a kit and some of its parts aren't in stock at Bedfordview. Create a pick so the warehouse knows where the parts come from, then complete the sale.`;
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              detail: {
                code: "kit_requires_pick",
                message,
                kits: [
                  {
                    sku_id: "sku-headboard",
                    sku_code: "P36410/2",
                    sku_name: kitName,
                    qty: 1,
                    location_id: "loc-bedford",
                    location_name: "Bedfordview",
                    reason: "split_pick",
                    message,
                  },
                ],
              },
            }),
            { status: 409, statusText: "Conflict" },
          ),
      ),
    );

    const error = await createTillSale({
      location_id: "loc-bedford",
      lines: [{ sku_id: "sku-headboard", qty: 1 }],
      tender: "cash",
    }).then(
      () => null,
      (caught: unknown) => caught,
    );

    expect(error).toBeInstanceOf(ApiError);
    const apiError = error as ApiError;
    expect(apiError.status).toBe(409);
    expect(apiError.message).toBe(message);
    const parsed = parseKitRequiresPick(apiError.detail);
    expect(parsed?.kits[0]?.sku_name).toBe(kitName);
    expect(parsed?.kits[0]?.sku_code).toBe("P36410/2");
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

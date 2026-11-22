import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api";
import { combineSaleReference, queryKeys } from "@/lib/queries";
import { createQueryClient, shouldRetry } from "@/lib/query-client";

describe("shouldRetry", () => {
  it("never retries a 4xx answer", () => {
    for (const status of [400, 401, 403, 404, 409, 422]) {
      expect(shouldRetry(0, new ApiError(status, "no"))).toBe(false);
    }
  });

  it("retries a server or network failure once", () => {
    expect(shouldRetry(0, new ApiError(503, "down"))).toBe(true);
    expect(shouldRetry(0, new TypeError("Failed to fetch"))).toBe(true);
    expect(shouldRetry(1, new ApiError(503, "down"))).toBe(false);
  });
});

describe("queryKeys", () => {
  it("are stable and distinct prefixes", () => {
    const keys = Object.values(queryKeys).map((key) => JSON.stringify(key));
    expect(new Set(keys).size).toBe(keys.length);
    expect(queryKeys.skus).toBe(queryKeys.skus);
    for (const a of Object.values(queryKeys)) {
      for (const b of Object.values(queryKeys)) {
        if (a === b) continue;
        // No key is a prefix of another, so invalidating one never refreshes a sibling.
        expect(JSON.stringify(b.slice(0, a.length))).not.toBe(JSON.stringify(a));
      }
    }
  });

  it("invalidating a key refreshes its filtered variants and nothing else", async () => {
    const client = createQueryClient();
    const filtered = [...queryKeys.customers, { archived: true }];
    for (const key of [...Object.values(queryKeys), filtered]) client.setQueryData(key, []);

    await client.invalidateQueries({ queryKey: queryKeys.customers });

    const invalidated = (key: readonly unknown[]) => client.getQueryState(key)?.isInvalidated;
    expect(invalidated(queryKeys.customers)).toBe(true);
    expect(invalidated(filtered)).toBe(true);
    for (const key of [queryKeys.skus, queryKeys.priceLists, queryKeys.settings, queryKeys.locations, queryKeys.salesStaffOptions]) {
      expect(invalidated(key)).toBe(false);
    }
  });

  it("sales staff edits reach the options list", async () => {
    const client = createQueryClient();
    client.setQueryData(queryKeys.salesStaffOptions, []);
    await client.invalidateQueries({ queryKey: ["sales-staff"] });
    expect(client.getQueryState(queryKeys.salesStaffOptions)?.isInvalidated).toBe(true);
  });
});

describe("combineSaleReference", () => {
  const ok = <T,>(data: T) => ({ data, error: null });
  const lists = [{ id: "list-1", name: "Trade" }] as never[];

  it("waits for all three", () => {
    expect(combineSaleReference([ok([]), { error: null }, ok(lists)]).data).toBeUndefined();
    expect(combineSaleReference([ok([]), ok([]), ok(lists)]).data?.priceLists).toEqual(lists);
  });

  it("reports the first failure", () => {
    const failure = new ApiError(500, "boom");
    expect(combineSaleReference([ok([]), { error: failure }, ok(lists)]).error).toBe(failure);
  });
});

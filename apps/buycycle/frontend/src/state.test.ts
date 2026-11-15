import { describe, expect, it, vi } from "vitest";
import {
  currentOriginExports,
  mergeLegacy,
  stable,
  validateLegacy,
  type BrowserState,
} from "./state";
import { returns, safeUrl } from "./format";
import type { Listing } from "./api/client";
const empty = (): BrowserState => ({
  version: 1,
  bikes: { watch: {}, log: [], costs: { bp: 2.5, sellfee: 6.95, relist: 0 } },
  wheels: { watch: {}, log: [], costs: { bp: 6, bpf: 1 } },
});
const watch = {
  n: "Synthetic bike",
  u: "https://example.invalid/bike",
  p: 1200,
  t: "2026-11-01",
  note: "preserve unknown field",
};
const trade = {
  name: "Synthetic wheel",
  url: "https://example.invalid/wheel",
  buy: 100,
  bd: "2026-11-01",
  sell: null,
  sd: null,
  extra_note: "retain",
};
describe("lossless browser-state migration preview", () => {
  it("preserves watches, duplicate trades, costs and unknown row metadata for both categories", () => {
    const docs = [
      {
        kind: "bikes" as const,
        document: {
          watch: { a: watch },
          log: [trade, trade],
          costs: { bp: 3, relist: 8 },
        },
      },
      {
        kind: "wheels" as const,
        document: { watch: { b: watch }, log: [trade], costs: { bpf: 2 } },
      },
    ];
    const first = mergeLegacy(empty(), docs, "replace");
    expect(first.errors).toEqual([]);
    expect(first.state.bikes.log).toHaveLength(2);
    expect(first.state.bikes.watch.a).toEqual(watch);
    expect(first.state.bikes.costs.relist).toBe(8);
    expect(first.state.wheels.costs.bpf).toBe(2);
    const second = mergeLegacy(first.state, docs, "replace");
    expect(second.state).toEqual(first.state);
    expect(second.counts.trades).toBe(0);
  });
  it("reports conflicts without mutating the original and applies only an explicit policy", () => {
    const current = empty();
    const before = stable(current);
    const docs = [{ kind: "bikes" as const, document: { costs: { bp: 9 } } }];
    expect(mergeLegacy(current, docs, "reject").conflicts).toEqual([
      "bikes: cost bp",
    ]);
    expect(
      mergeLegacy(current, docs, "keep_existing").state.bikes.costs.bp,
    ).toBe(2.5);
    expect(mergeLegacy(current, docs, "replace").state.bikes.costs.bp).toBe(9);
    expect(stable(current)).toBe(before);
  });
  it("rejects invalid/unknown category data rather than silently discarding it", () => {
    expect(validateLegacy({ costs: { bp: -1 } })).not.toEqual([]);
    expect(validateLegacy({ costs: { bp: 101 } })).not.toEqual([]);
    expect(validateLegacy({ unexpected: "retain original" })).not.toEqual([]);
    expect(validateLegacy({ log: [{ buy: null }] })).not.toEqual([]);
  });
  it("exports both categories from this origin using reads only", () => {
    vi.stubGlobal("location", { origin: "http://127.0.0.1:8095" });
    const getItem = vi.fn((key: string) =>
      key === "bikes:watch" ? JSON.stringify({ a: watch }) : null,
    );
    const result = currentOriginExports({ getItem });
    expect(getItem).toHaveBeenCalledTimes(6);
    expect(result.documents[0]?.document).toMatchObject({
      watch: { a: watch },
    });
    expect(result.documents.map((d) => d.kind)).toEqual(["bikes", "wheels"]);
    expect(result.origin).toBe("http://127.0.0.1:8095");
    vi.unstubAllGlobals();
  });
});
describe("display calculations and links", () => {
  it("retains full legacy cost formula and missing reference semantics", () => {
    const item = { price: 100, reference_price: 200 } as Listing;
    const costs = {
      bp: 2,
      bpf: 1,
      pay: 3,
      shipin: 4,
      pack: 5,
      repair: 6,
      buffer: 7,
      haircut: 10,
      sellfee: 8,
      shipout: 9,
      relist: 10,
    };
    const total = 100 * 1.02 + 1 + 100 * 0.03 + 4 + 5 + 6 + 7;
    const profit = 200 * 0.9 * 0.92 - 9 - 10 - total;
    expect(returns(item, costs).profit).toBeCloseTo(profit);
    expect(returns(item, costs).roi).toBeCloseTo((profit / total) * 100);
    expect(returns({ ...item, reference_price: null }, costs)).toEqual({
      profit: null,
      roi: null,
    });
  });
  it("blocks executable URL schemes", () => {
    expect(safeUrl("javascript:alert(1)")).toBeUndefined();
    expect(safeUrl("https://example.invalid/")).toBe(
      "https://example.invalid/",
    );
  });
});

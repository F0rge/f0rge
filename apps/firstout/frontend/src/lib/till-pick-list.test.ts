import { describe, expect, it } from "vitest";

import type { PickDefaultAllocations, PickLine } from "./picks";
import {
  confirmedTitle,
  defaultsPatch,
  isLineChanged,
  noStockNote,
  sourceOptionText,
  sourcePatch,
  whatHappensNext,
} from "./till-pick-list";

const NAMES: Record<string, string> = { wh: "Warehouse", bv: "Bedfordview", kv: "Kramerville" };
const line = (sku: string, name: string, need: number, cells: Record<string, number>): PickLine => ({
  sku_id: sku,
  sku_our_ref: sku.toUpperCase(),
  sku_name: name,
  qty_needed: need,
  allocations: Object.entries(cells).map(([location_id, qty]) => ({
    location_id, location_name: NAMES[location_id], on_hand: 5, qty,
  })),
});
const sofa = line("sofa", "Sofa", 1, { wh: 1, bv: 0 });
const lamp = line("lamp", "Floor lamp", 2, { wh: 0, bv: 2 });
const split = line("rug", "Rug", 3, { wh: 2, kv: 1 });
const defaults: PickDefaultAllocations = {
  lines: [
    { sku_id: "sofa", allocations: [{ location_id: "wh", location_name: "Warehouse", qty: 1 }] },
    { sku_id: "lamp", allocations: [{ location_id: "wh", location_name: "Warehouse", qty: 2 }] },
    { sku_id: "rug", allocations: [
      { location_id: "kv", location_name: "Kramerville", qty: 1 },
      { location_id: "wh", location_name: "Warehouse", qty: 2 },
    ] },
  ],
};

describe("changed detection", () => {
  it("compares the allocated sources with the defaults, ignoring qty 0 cells and order", () => {
    expect(isLineChanged(sofa, defaults)).toBe(false);
    expect(isLineChanged(lamp, defaults)).toBe(true);
    expect(isLineChanged(split, defaults)).toBe(false);
  });
  it("never marks a line changed while the defaults are unknown", () => {
    expect(isLineChanged(lamp, null)).toBe(false);
  });
});

describe("PATCH bodies", () => {
  it("moves one line's whole qty to the chosen source and keeps every other line as is", () => {
    expect(sourcePatch([sofa, lamp, split], "lamp", "kv")).toEqual({
      lines: [
        { sku_id: "sofa", allocations: [{ location_id: "wh", qty: 1 }] },
        { sku_id: "lamp", allocations: [{ location_id: "kv", qty: 2 }] },
        { sku_id: "rug", allocations: [{ location_id: "wh", qty: 2 }, { location_id: "kv", qty: 1 }] },
      ],
    });
  });
  it("resets every line to the defaults, empty when the allocator has none", () => {
    expect(defaultsPatch([sofa, lamp, line("chair", "Chair", 1, {})], defaults)).toEqual({
      lines: [
        { sku_id: "sofa", allocations: [{ location_id: "wh", qty: 1 }] },
        { sku_id: "lamp", allocations: [{ location_id: "wh", qty: 2 }] },
        { sku_id: "chair", allocations: [] },
      ],
    });
  });
});

describe("source options", () => {
  it("labels options with on-hand, default and this showroom", () => {
    const cell = { location_id: "bv", location_name: "Bedfordview", on_hand: 3, qty: 0 };
    expect(sourceOptionText(cell, { isDefault: true, isShowroom: true }))
      .toBe("Bedfordview · 3 on hand · default · this showroom");
    expect(sourceOptionText(cell, { isDefault: false, isShowroom: false }))
      .toBe("Bedfordview · 3 on hand");
  });
});

describe("after confirming", () => {
  it("counts lines and source locations", () => {
    expect(confirmedTitle("PCK-0007", [sofa, lamp])).toBe("Pick PCK-0007 confirmed · 2 lines from 2 locations");
    expect(confirmedTitle("PCK-0008", [sofa])).toBe("Pick PCK-0008 confirmed · 1 line from 1 location");
  });
  it("says per source location what happens next", () => {
    const types = new Map([["wh", "warehouse"], ["bv", "showroom"], ["kv", "showroom"]]);
    expect(whatHappensNext([sofa, lamp, split], types, "bv")).toEqual([
      { locationId: "wh", heading: "Warehouse — Sofa ×1, Rug ×2", detail: "picked at Warehouse, then staged" },
      { locationId: "bv", heading: "Bedfordview — Floor lamp ×2", detail: "staged for collection or delivery from here" },
      { locationId: "kv", heading: "Kramerville — Rug ×1", detail: "staged for collection or delivery from Kramerville" },
    ]);
  });
});

describe("no stock needed note", () => {
  it("names the lines left off the pick list", () => {
    expect(noStockNote([])).toBeNull();
    expect(noStockNote(["DELIVERY JHB (S001)"]))
      .toBe("DELIVERY JHB (S001) needs no stock, so it is not on the pick list.");
    expect(noStockNote(["A (1)", "B (2)", "C (3)"]))
      .toBe("A (1), B (2) and C (3) need no stock, so they are not on the pick list.");
  });
});

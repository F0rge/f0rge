import { describe, expect, it } from "vitest";

import type { InventorySku, Location } from "@/lib/api";

import {
  formatStockQty,
  matchesPipelineChips,
  matchesStockSearch,
  showroomAvailable,
  visibleBins,
} from "./stock-table";

const locations: Location[] = [
  {
    id: "wh-1",
    name: "Kramerville",
    type: "warehouse",
    is_archived: false,
    archived_at: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "sh-1",
    name: "Bedfordview",
    type: "showroom",
    is_archived: false,
    archived_at: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

const entry: InventorySku = {
  sku_id: "sku-1",
  our_ref: "PG-CHAIR",
  name: "Playground dining chair",
  on_order: 2,
  on_hand: 2,
  sellable: true,
  unit_cost_zar: "105.0000",
  locations: [
    {
      location_id: "wh-1",
      location_name: "Kramerville",
      on_hand: 2,
      unit_cost_zar: "105.0000",
      bins: [{ bin_id: "bin-1", code: "FLOOR", on_hand: 2 }],
    },
    {
      location_id: "sh-1",
      location_name: "Bedfordview",
      on_hand: 0,
      unit_cost_zar: null,
      bins: [{ bin_id: "bin-2", code: "FLOOR", on_hand: 0 }],
    },
  ],
};

describe("stock-table helpers", () => {
  it("formats zero qty as em dash", () => {
    expect(formatStockQty(0)).toBe("—");
    expect(formatStockQty(3)).toBe("3");
  });

  it("filters by search and pipeline chips with OR logic", () => {
    expect(matchesStockSearch(entry, "chair")).toBe(true);
    expect(matchesStockSearch(entry, "missing")).toBe(false);
    expect(matchesPipelineChips(entry, ["on_water"], locations)).toBe(true);
    expect(matchesPipelineChips(entry, ["at_showroom"], locations)).toBe(false);
    expect(matchesPipelineChips(entry, ["at_showroom", "at_warehouse"], locations)).toBe(true);
  });

  it("reads showroom availability from Bedfordview", () => {
    expect(showroomAvailable(entry, locations[1])).toBe(0);
    const atShowroom: InventorySku = {
      ...entry,
      locations: [
        entry.locations[0],
        { ...entry.locations[1], on_hand: 1 },
      ],
    };
    expect(showroomAvailable(atShowroom, locations[1])).toBe(1);
  });

  it("hides single default bin rows", () => {
    expect(visibleBins(entry.locations[0].bins)).toEqual([]);
    expect(
      visibleBins([
        { bin_id: "a", code: "FLOOR", on_hand: 1 },
        { bin_id: "b", code: "A-01-1", on_hand: 2 },
      ]),
    ).toHaveLength(2);
  });
});

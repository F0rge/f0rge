import { describe, expect, it } from "vitest";

import type { InventorySku } from "./api";
import { basketStockNote, namedLocations, resultStockState } from "./till-stock-notes";
import { tillAvailability } from "./till-reservations";

const sellable = new Set(["here", "wh", "kram", "pta"]);
const rowOf = (stock: Record<string, number>) => ({
  sku_id: "sofa",
  locations: Object.entries(stock).map(([location_id, on_hand]) => ({
    location_id, on_hand,
    location_name: { here: "Bedfordview", wh: "Warehouse", kram: "Kramerville", pta: "Pretoria", gone: "Archived" }[location_id],
  })),
}) as InventorySku;

function result(stock: Record<string, number>, inCart = 0) {
  const row = rowOf(stock);
  const base = { row, locationId: "here", locationName: "Bedfordview", sellableLocationIds: sellable, inCart };
  return resultStockState(base, tillAvailability({ ...base, reservation: undefined }));
}

describe("location naming", () => {
  it("names at most two locations, then how many more", () => {
    expect(namedLocations([])).toBe("another location");
    expect(namedLocations(["Warehouse"])).toBe("Warehouse");
    expect(namedLocations(["Warehouse", "Kramerville"])).toBe("Warehouse, Kramerville");
    expect(namedLocations(["Warehouse", "Kramerville", "Pretoria"])).toBe("Warehouse, Kramerville +1 more");
  });
});

describe("search result stock state", () => {
  it("counts what the showroom still has after the cart", () => {
    expect(result({ here: 4, wh: 3 })).toBe("4 at Bedfordview");
    expect(result({ here: 4 }, 1)).toBe("3 at Bedfordview");
  });

  it("says low stock when one or fewer are left here", () => {
    expect(result({ here: 1, wh: 5 })).toBe("Low stock · last 1 at Bedfordview");
    expect(result({ here: 3 }, 2)).toBe("Low stock · last 1 at Bedfordview");
  });

  it("names the other locations with stock, most first, ignoring inactive ones", () => {
    expect(result({ wh: 1 })).toBe("Not at Bedfordview · 1 at Warehouse");
    expect(result({ here: 0, kram: 1, wh: 2, gone: 9 })).toBe("Not at Bedfordview · 3 at Warehouse, Kramerville");
    expect(result({ kram: 1, wh: 2, pta: 1 })).toBe("Not at Bedfordview · 4 at Warehouse, Kramerville +1 more");
    expect(result({ here: 1, wh: 2 }, 1)).toBe("Not at Bedfordview · 2 at Warehouse");
  });

  it("shows the reservation reason when other sales block it", () => {
    const row = rowOf({ wh: 1 });
    const base = { row, locationId: "here", locationName: "Bedfordview", sellableLocationIds: sellable, inCart: 0 };
    const availability = tillAvailability({
      ...base,
      reservation: {
        sku_id: "sofa", reserved_by_others: 1,
        blocking: { location_id: "kram", location_name: "Kramerville", holder_kind: "invoice", expires_at: null },
      },
    });
    expect(resultStockState(base, availability)).toBe("Reserved for an invoice at Kramerville");
  });

  it("says when the cart already holds all of it", () => {
    expect(result({ here: 1, wh: 1 }, 2)).toBe("All in this sale");
  });
});

describe("basket stock note", () => {
  const note = (stock: Record<string, number>, inCart: number) => basketStockNote({
    row: rowOf(stock), locationId: "here", locationName: "Bedfordview", sellableLocationIds: sellable, inCart,
  });

  it("is silent when the showroom covers the line with stock to spare", () => {
    expect(note({ here: 4 }, 2)).toBeNull();
  });

  it("notes a line sold entirely from elsewhere", () => {
    expect(note({ wh: 3 }, 1)).toBe("Not at Bedfordview · 1 at Warehouse");
  });

  it("splits a line partly at the showroom", () => {
    expect(note({ here: 1, wh: 3 }, 3)).toBe("1 here · 2 from Warehouse");
    expect(note({ here: 1, wh: 1, kram: 1 }, 3)).toBe("1 here · 2 from Warehouse, Kramerville");
  });

  it("notes low stock when the line leaves one or fewer here", () => {
    expect(note({ here: 1 }, 1)).toBe("Low stock · last 1 at Bedfordview");
    expect(note({ here: 3 }, 2)).toBe("Low stock · last 3 at Bedfordview");
  });
});

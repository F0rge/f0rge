import { describe, expect, it } from "vitest";

import { reorderExplanation } from "./reorder";

describe("reorderExplanation", () => {
  it("explains a rounded suggestion with the supplier's terms", () => {
    expect(reorderExplanation({ need_qty: 7, suggested_qty: 12, min_order_qty: 12, pack_multiple: 2 }))
      .toBe("Needs 7, rounded to 12 (minimum order 12, packs of 2)");
    expect(reorderExplanation({ need_qty: 7, suggested_qty: 8, min_order_qty: null, pack_multiple: 2 }))
      .toBe("Needs 7, rounded to 8 (packs of 2)");
  });

  it("says nothing when the suggestion is the need", () => {
    expect(reorderExplanation({ need_qty: 7, suggested_qty: 7, min_order_qty: 1, pack_multiple: 1 })).toBeNull();
    expect(reorderExplanation({ need_qty: 7, suggested_qty: 7, min_order_qty: null, pack_multiple: null })).toBeNull();
  });
});

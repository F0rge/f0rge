import { describe, expect, it } from "vitest";

import { ApiError } from "./api";
import {
  breaksQuantityRule,
  lineQuantityNotice,
  quantityInputBounds,
  quantityRuleHelper,
  quantityRuleRefusal,
  snapQty,
  startQty,
} from "./sale-quantity-rule";

const pair = { sell_multiple: 2, min_sell_qty: 2 };
const pairsOfFour = { sell_multiple: 2, min_sell_qty: 4 };
const minimumThree = { sell_multiple: 1, min_sell_qty: 3 };
const single = { sell_multiple: 1, min_sell_qty: 1 };

describe("quantityRuleHelper", () => {
  it("explains the rule in shop words", () => {
    expect(quantityRuleHelper(pairsOfFour)).toBe("Sold in multiples of 2, minimum 4");
    expect(quantityRuleHelper(pair)).toBe("Sold in multiples of 2");
    expect(quantityRuleHelper(minimumThree)).toBe("Minimum quantity 3");
    expect(quantityRuleHelper(single)).toBeNull();
    expect(quantityRuleHelper({})).toBeNull();
  });
});

describe("stepping and validity", () => {
  it("starts at the minimum and snaps up to the next valid quantity", () => {
    expect(startQty(pairsOfFour)).toBe(4);
    expect(startQty(single)).toBe(1);
    expect(snapQty(pairsOfFour, 1)).toBe(4);
    expect(snapQty(pairsOfFour, 5)).toBe(6);
    expect(snapQty(pair, 6)).toBe(6);
  });

  it("flags quantities off the multiple or below the minimum", () => {
    expect(breaksQuantityRule(pairsOfFour, 2)).toBe(true);
    expect(breaksQuantityRule(pairsOfFour, 5)).toBe(true);
    expect(breaksQuantityRule(pairsOfFour, 6)).toBe(false);
    expect(breaksQuantityRule(minimumThree, 4)).toBe(false);
  });

  it("lets an override holder go below the minimum but keeps the step", () => {
    expect(quantityInputBounds(pairsOfFour, false)).toEqual({ min: 4, step: 2 });
    expect(quantityInputBounds(pairsOfFour, true)).toEqual({ min: 1, step: 2 });
  });
});

const refusalError = new ApiError(409, "Oslo dining chair is sold in multiples of 2, minimum 4.", {
  code: "sale_quantity_rule",
  message: "Oslo dining chair is sold in multiples of 2, minimum 4.",
  lines: [{ sku_id: "oslo", our_ref: "OSLO-01", name: "Oslo dining chair", qty: 3, sell_multiple: 2, min_sell_qty: 4,
    message: "Oslo dining chair is sold in multiples of 2, minimum 4." }],
});

describe("quantityRuleRefusal", () => {
  it("maps the 409 lines by SKU", () => {
    expect(quantityRuleRefusal(refusalError)).toEqual({
      message: "Oslo dining chair is sold in multiples of 2, minimum 4.",
      lines: { oslo: { qty: 3, message: "Oslo dining chair is sold in multiples of 2, minimum 4." } },
    });
  });

  it("ignores other failures", () => {
    expect(quantityRuleRefusal(new ApiError(409, "x", { code: "kit_requires_pick" }))).toBeNull();
    expect(quantityRuleRefusal(new ApiError(400, "x"))).toBeNull();
    expect(quantityRuleRefusal(new Error("x"))).toBeNull();
  });
});

describe("lineQuantityNotice", () => {
  const refusal = quantityRuleRefusal(refusalError);

  it("blocks when the preview refuses and informs an override holder", () => {
    expect(lineQuantityNotice({ blocked_by: "quantity_rule", quantity_rule: "m" }, null, "oslo", 3))
      .toEqual({ kind: "error", message: "m" });
    expect(lineQuantityNotice({ blocked_by: null, quantity_rule: "m" }, null, "oslo", 3))
      .toEqual({ kind: "info", message: "m" });
  });

  it("shows a save refusal only while the line keeps the refused quantity", () => {
    expect(lineQuantityNotice(undefined, refusal, "oslo", 3)?.kind).toBe("error");
    expect(lineQuantityNotice(undefined, refusal, "oslo", 4)).toBeNull();
    expect(lineQuantityNotice(undefined, refusal, "other", 3)).toBeNull();
    expect(lineQuantityNotice({ blocked_by: null, quantity_rule: null }, refusal, "oslo", 4)).toBeNull();
  });
});

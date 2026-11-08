import { describe, expect, it } from "vitest";

import {
  clearTillCart,
  loadTillCart,
  nextTillStateAfterKitConfirm,
  openPicksHrefForKit,
  parseKitRequiresPick,
  salePickIds,
  saveTillCart,
  type TillCartSnapshot,
  type TillKitBlock,
} from "./till-kit-pick";

function memoryStore() {
  const data = new Map<string, string>();
  return {
    getItem: (key: string) => data.get(key) ?? null,
    setItem: (key: string, value: string) => {
      data.set(key, value);
    },
    removeItem: (key: string) => {
      data.delete(key);
    },
  };
}

const flower: TillKitBlock = {
  sku_id: "sku-flower",
  sku_code: "P72085ORC",
  sku_name: "Flower Arrangement P72085 + 6x5W + 3xL",
  qty: 1,
  location_id: "loc-bedford",
  location_name: "Bedfordview",
  reason: "split_pick",
  message:
    "Flower Arrangement P72085 + 6x5W + 3xL (P72085ORC) is a kit and some of its parts aren't in stock at Bedfordview. Create a pick so the warehouse knows where the parts come from, then complete the sale.",
};

const headboard: TillKitBlock = {
  sku_id: "sku-headboard",
  sku_code: "P36410/2",
  sku_name: "Eva Headboard Grey w/ base 206*172cm",
  qty: 1,
  location_id: "loc-bedford",
  location_name: "Bedfordview",
  reason: "missing_parts",
  message:
    "Eva Headboard Grey w/ base 206*172cm (P36410/2) is a kit and some of its parts aren't in stock at Bedfordview or anywhere else. Receive the missing parts before this kit can be sold.",
};

describe("parseKitRequiresPick", () => {
  it("reads a single split-pick block and a missing-parts block", () => {
    const parsed = parseKitRequiresPick({
      code: "kit_requires_pick",
      message: `${flower.message} ${headboard.message}`,
      kits: [flower, headboard],
    });
    expect(parsed).not.toBeNull();
    expect(parsed?.kits.map((kit) => kit.reason)).toEqual(["split_pick", "missing_parts"]);
    expect(parsed?.kits[0]?.sku_code).toBe("P72085ORC");
    expect(parsed?.kits[1]?.sku_name).toContain("Eva Headboard");
    expect(parsed?.message).toContain("P72085ORC");
    expect(parsed?.message).toContain("P36410/2");
  });

  it("ignores a plain string error", () => {
    expect(parseKitRequiresPick("Kit requires pick")).toBeNull();
  });
});

describe("open picks target", () => {
  it("links each kit, including one that is not first in the cart", () => {
    const hrefs = [headboard, flower].map(openPicksHrefForKit);
    expect(hrefs[0]).toBe("/picks?sku=sku-headboard&qty=1");
    expect(hrefs[1]).toBe("/picks?sku=sku-flower&qty=1");
    expect(hrefs[1]).not.toContain("sku-headboard");
  });
});

describe("confirming a kit pick", () => {
  it("keeps the cart, selects that pick, and drops only that kit from the error", () => {
    const cart = [
      { skuId: "sku-headboard", qty: 1 },
      { skuId: "sku-carver", qty: 1 },
      { skuId: "sku-flower", qty: 1 },
    ];
    const next = nextTillStateAfterKitConfirm(
      {
        cart,
        pickId: "",
        linkedPickIds: {},
        blocks: [headboard, flower],
      },
      { id: "pick-flower", skuId: flower.sku_id },
    );
    expect(next.cart).toEqual(cart);
    expect(next.pickId).toBe("pick-flower");
    expect(next.linkedPickIds).toEqual({ "sku-flower": "pick-flower" });
    expect(next.blocks.map((block) => block.sku_id)).toEqual(["sku-headboard"]);
    expect(salePickIds(next.linkedPickIds, next.pickId)).toEqual(["pick-flower"]);
  });

  it("sends every confirmed kit pick, not only the last one selected", () => {
    const ids = salePickIds(
      { "sku-flower": "pick-flower", "sku-headboard": "pick-headboard" },
      "pick-flower",
    );
    expect(ids).toEqual(["pick-flower", "pick-headboard"]);
  });
});

describe("till cart snapshot", () => {
  it("round-trips the cart and the selected pick", () => {
    const store = memoryStore();
    const snapshot: TillCartSnapshot = {
      locationId: "loc-bedford",
      customerId: "cust-changing-spaces",
      pickId: "pick-flower",
      linkedPickIds: { "sku-flower": "pick-flower" },
      lines: [
        { skuId: "sku-headboard", qty: 1, discountPercent: 33 },
        { skuId: "sku-flower", qty: 1, discountPercent: 0 },
      ],
    };
    saveTillCart(snapshot, store);
    expect(loadTillCart(store)).toEqual(snapshot);
    clearTillCart(store);
    expect(loadTillCart(store)).toBeNull();
  });
});

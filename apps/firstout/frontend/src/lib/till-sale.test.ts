import { describe, expect, it } from "vitest";

import type { CartLine } from "@/components/cart-editor";

import { ApiError, type CustomerCrm, type Sku, type TillSalePayload, type TillSaleResult } from "./api";
import type { TillKitBlock } from "./till-kit-pick";
import {
  completeTillSale,
  EMPTY_SALE,
  tillPriceRequest,
  tillSaleReducer,
  type TillCheckout,
  type TillSale,
} from "./till-sale";

const line = (id: string, qty = 1, discountPercent = 0): CartLine =>
  ({ key: id, sku: { id } as Sku, qty, discountPercent });

const kit: TillKitBlock = {
  sku_id: "kit", sku_code: "K1", sku_name: "Kit", qty: 1, location_id: "here", location_name: "Here",
  reason: "split_pick", message: "Kit needs a pick.",
};

/** A sale with every field away from empty. */
const busy: TillSale = {
  cart: [line("sofa", 2, 10)],
  customerId: "acme",
  commitmentCustomer: { id: "acme" } as CustomerCrm,
  pickId: "pick-1",
  linkedPickIds: { kit: "pick-1" },
  heldNote: "held",
  notePrinted: "  Deliver Friday  ",
  noteInternal: " gate code 12 ",
  salesStaffId: "thandi",
  quoteId: "quote-1",
  resumedSale: true,
  kitBlocks: [kit],
  creditBlock: "Customer is on hold",
  creditOverride: true,
  creditOverrideReason: " paid in cash ",
  dueDateEdit: { customerId: "acme", value: "2026-12-31" },
  skuId: "chair",
  qty: 3,
};

describe("till sale state", () => {
  it("reset clears the whole sale and keeps only the colleague", () => {
    expect(tillSaleReducer(busy, { type: "reset" })).toEqual({ ...EMPTY_SALE, salesStaffId: "thandi" });
    expect(tillSaleReducer(EMPTY_SALE, { type: "reset" })).toEqual(EMPTY_SALE);
  });

  it("restore replaces what the basket saves and leaves the cashier's work", () => {
    const restored = tillSaleReducer(busy, {
      type: "restore",
      snapshot: { locationId: "here", customerId: "acme", pickId: "", linkedPickIds: {}, quoteId: "", lines: [] },
      lines: [line("bed")],
      customer: null,
    });
    expect(restored).toEqual({
      ...busy,
      cart: [line("bed")], commitmentCustomer: null, pickId: "", linkedPickIds: {}, heldNote: "",
      notePrinted: "", noteInternal: "", salesStaffId: "", quoteId: "",
    });
  });

  it("a restored basket for another customer drops the credit decision", () => {
    const restored = tillSaleReducer(busy, {
      type: "restore",
      snapshot: { locationId: "here", customerId: "globex", pickId: "", linkedPickIds: {}, lines: [] },
      lines: [],
      customer: null,
    });
    expect(restored).toMatchObject({
      customerId: "globex", creditOverride: false, creditOverrideReason: "", creditBlock: null,
      dueDateEdit: busy.dueDateEdit, kitBlocks: [kit],
    });
  });

  it("another customer gets their own credit decision", () => {
    const same = tillSaleReducer(busy, { type: "edit", change: { notePrinted: "x" } });
    expect(same).toMatchObject({ creditOverride: true, creditOverrideReason: " paid in cash ", creditBlock: "Customer is on hold" });
    const other = tillSaleReducer(busy, { type: "edit", change: (sale) => ({ customerId: `${sale.customerId}-2` }) });
    expect(other).toMatchObject({ customerId: "acme-2", creditOverride: false, creditOverrideReason: "", creditBlock: null });
  });
});

const result = { invoice_id: "inv-1" } as TillSaleResult;
const checkout: TillCheckout = {
  locationId: "here", tender: "cash", dueDate: "2026-12-31", priceRevision: "rev-1", canOverrideCredit: false,
};

async function sell(sale: TillSale, overrides: Partial<TillCheckout> = {}, create?: () => Promise<TillSaleResult>) {
  const bodies: TillSalePayload[] = [];
  const outcome = await completeTillSale({
    flush: async () => ({ id: "basket-1", version: 7 }),
    create: (body) => {
      bodies.push(body);
      return create ? create() : Promise.resolve(result);
    },
  }, sale, { ...checkout, ...overrides });
  return { outcome, body: bodies[0] };
}

describe("till price preview request", () => {
  it("sends the quote and the held basket, as the sale does, so kept quantities are not flagged", () => {
    expect(tillPriceRequest([line("sofa", 3)], "", { quoteId: "quote-1", basketId: "basket-1" })).toEqual({
      quote_id: "quote-1", basket_id: "basket-1", lines: [{ sku_id: "sofa", qty: 3 }],
    });
    expect(tillPriceRequest([line("sofa")], "cust", { quoteId: "", basketId: null })).toEqual({
      customer_id: "cust", lines: [{ sku_id: "sofa", qty: 1 }],
    });
  });
});

describe("till sale request", () => {
  it("sends a walk-in cash sale with nothing optional", async () => {
    const { outcome, body } = await sell({ ...EMPTY_SALE, cart: [line("sofa")] });
    expect(outcome).toEqual({ kind: "sold", result });
    expect(body).toEqual({
      location_id: "here", basket_id: "basket-1", basket_version: 7, price_revision: "rev-1", tender: "cash",
      lines: [{ sku_id: "sofa", qty: 1 }],
    });
  });

  it("sends an account sale on statement with its due date, notes, colleague, quote and picks", async () => {
    const { body } = await sell(busy, { tender: "statement", salesStaffId: "thandi", canOverrideCredit: true });
    expect(body).toEqual({
      location_id: "here", basket_id: "basket-1", basket_version: 7, price_revision: "rev-1",
      customer_id: "acme", lines: [{ sku_id: "sofa", qty: 2, discount_percent: 10 }],
      tender: "statement", due_date: "2026-12-31",
      note_printed: "Deliver Friday", note_internal: "gate code 12",
      sales_staff_id: "thandi", quote_id: "quote-1", pick_id: "pick-1", pick_ids: ["pick-1"],
    });
  });

  it("sends a credit override only on a paid sale by someone allowed to give it", async () => {
    expect((await sell(busy, { tender: "card", canOverrideCredit: true })).body).toMatchObject({
      tender: "card", credit_override: true, credit_override_reason: "paid in cash",
    });
    const card = (await sell(busy, { tender: "card" })).body;
    expect(card).not.toHaveProperty("credit_override");
    expect(card).not.toHaveProperty("due_date");
    expect((await sell({ ...busy, creditOverride: false }, { tender: "eft", canOverrideCredit: true })).body)
      .not.toHaveProperty("credit_override");
  });

  it("leaves out blank notes and a colleague nobody chose", async () => {
    const { body } = await sell({ ...busy, notePrinted: "  ", noteInternal: "", quoteId: "", pickId: "", linkedPickIds: {} });
    for (const key of ["note_printed", "note_internal", "sales_staff_id", "quote_id", "pick_id", "pick_ids"]) {
      expect(body).not.toHaveProperty(key);
    }
  });
});

describe("till sale outcome", () => {
  const refuse = (error: unknown) => () => Promise.reject(error);

  it("names each 409 the server explains", async () => {
    const cases: [unknown, unknown][] = [
      [new ApiError(409, "Prices changed", { code: "till_price_conflict", message: "Prices changed" }),
        { kind: "price_conflict", message: "Prices changed" }],
      [new ApiError(409, "Customer is on hold", { code: "customer_credit_blocked", message: "Customer is on hold" }),
        { kind: "credit_block", message: "Customer is on hold" }],
      [new ApiError(409, "Kit needs a pick.", { code: "kit_requires_pick", message: "Kit needs a pick.", kits: [kit] }),
        { kind: "kit_requires_pick", kits: [kit] }],
      [new ApiError(409, "Pairs only", { code: "sale_quantity_rule", message: "Pairs only",
        lines: [{ sku_id: "chair", qty: 1, message: "Pairs only" }] }),
        { kind: "quantity_rule", message: "Pairs only", refusal: { message: "Pairs only", lines: { chair: { qty: 1, message: "Pairs only" } } } }],
      [new ApiError(409, "Bad kit", { code: "kit_requires_pick", kits: [{ sku_id: "kit" }] }),
        { kind: "error", message: "Bad kit" }],
      [new ApiError(409, "Customer is on hold", "Customer is on hold"), { kind: "error", message: "Customer is on hold" }],
      [new ApiError(500, "POST /till/sales failed (500)"), { kind: "error", message: "POST /till/sales failed (500)" }],
      ["boom", { kind: "error", message: "Sale failed." }],
    ];
    for (const [error, outcome] of cases) {
      expect((await sell(busy, {}, refuse(error))).outcome).toEqual(outcome);
    }
  });

  it("hands a basket conflict back whole, from the save or the sale", async () => {
    const conflict = new ApiError(409, "Expired", { code: "basket_expired", basket: null });
    expect((await sell(busy, {}, refuse(conflict))).outcome).toEqual({ kind: "basket_conflict", error: conflict });
    const create = () => Promise.resolve(result);
    const outcome = await completeTillSale({ flush: () => Promise.reject(conflict), create }, busy, checkout);
    expect(outcome).toEqual({ kind: "basket_conflict", error: conflict });
  });
});

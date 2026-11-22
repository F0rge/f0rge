import type { CartLine } from "@/components/cart-editor";

import {
  conflictCode,
  type CustomerCrm,
  type TillPriceRequest,
  type TillSalePayload,
  type TillSaleResult,
  type TillTender,
} from "./api";
import { isBasketConflict, type SavedBasket } from "./till-basket";
import { parseKitRequiresPick, salePickIds, type TillCartSnapshot, type TillKitBlock } from "./till-kit-pick";

/**
 * The till's sale: one module owns its fields, how it is cleared, what is sent to sell it and
 * what the server's answer means. The page renders it and wires the buttons.
 */
export type TillSale = {
  // Saved with the server basket: `restore` replaces exactly these.
  cart: CartLine[];
  customerId: string;
  /** A customer outside the loaded list that a basket, pick or quote brought in. */
  commitmentCustomer: CustomerCrm | null;
  pickId: string;
  linkedPickIds: Record<string, string>;
  heldNote: string;
  notePrinted: string;
  noteInternal: string;
  /** Who made the sale (commission). Survives `reset`: the next sale is usually theirs too. */
  salesStaffId: string;
  /** The open quote this sale converts. */
  quoteId: string;
  // This sale only.
  resumedSale: boolean;
  kitBlocks: TillKitBlock[];
  creditBlock: string | null;
  creditOverride: boolean;
  creditOverrideReason: string;
  /** A typed due date belongs to the customer it was typed for; a new customer gets their terms. */
  dueDateEdit: { customerId: string; value: string } | null;
  /** The finder's pending product and quantity. */
  skuId: string;
  qty: number | "";
};

export const EMPTY_SALE: TillSale = {
  cart: [], customerId: "", commitmentCustomer: null, pickId: "", linkedPickIds: {}, heldNote: "",
  notePrinted: "", noteInternal: "", salesStaffId: "", quoteId: "", resumedSale: false, kitBlocks: [],
  creditBlock: null, creditOverride: false, creditOverrideReason: "", dueDateEdit: null, skuId: "", qty: 1,
};

export type TillSaleAction =
  /** Field edits; a function sees the current sale. */
  | { type: "edit"; change: Partial<TillSale> | ((sale: TillSale) => Partial<TillSale>) }
  /** A new, empty sale: after a sale, a hold, a resume and a showroom change. */
  | { type: "reset" }
  /** Show a basket the server holds; what the cashier is doing that the basket does not save stays. */
  | { type: "restore"; snapshot: TillCartSnapshot; lines: CartLine[]; customer: CustomerCrm | null };

export function tillSaleReducer(sale: TillSale, action: TillSaleAction): TillSale {
  let next: TillSale;
  if (action.type === "reset") {
    next = { ...EMPTY_SALE, salesStaffId: sale.salesStaffId };
  } else if (action.type === "restore") {
    const { snapshot } = action;
    next = {
      ...sale,
      cart: action.lines,
      commitmentCustomer: action.customer,
      customerId: snapshot.customerId,
      pickId: snapshot.pickId,
      linkedPickIds: snapshot.linkedPickIds,
      heldNote: snapshot.note ?? "",
      notePrinted: snapshot.notePrinted ?? "",
      noteInternal: snapshot.noteInternal ?? "",
      salesStaffId: snapshot.salesStaffId ?? "",
      quoteId: snapshot.quoteId ?? "",
    };
  } else {
    next = { ...sale, ...(typeof action.change === "function" ? action.change(sale) : action.change) };
  }
  // Another customer gets their own credit decision.
  return next.customerId === sale.customerId
    ? next
    : { ...next, creditOverride: false, creditOverrideReason: "", creditBlock: null };
}

/** What the server prices; the preview query is keyed on it. */
export function tillPriceRequest(cart: CartLine[], customerId: string): TillPriceRequest {
  return {
    ...(customerId ? { customer_id: customerId } : {}),
    lines: cart.map((line) => ({
      sku_id: line.sku.id,
      qty: line.qty,
      ...(line.discountPercent > 0 ? { discount_percent: line.discountPercent } : {}),
    })),
  };
}

/** An override applies to paid sales only, by someone allowed to give it. */
export function creditOverrideActive(sale: TillSale, tender: TillTender, canOverrideCredit: boolean): boolean {
  return tender !== "statement" && canOverrideCredit && sale.creditOverride;
}

/** The till's choices the sale does not hold. */
export type TillCheckout = {
  locationId: string;
  tender: TillTender;
  /** Sent only on statement. */
  dueDate: string;
  /** The preview's revision: the server refuses the sale if its prices moved since. */
  priceRevision: string;
  /** The validated colleague (one the business lists); the sale's own id is only the selection. */
  salesStaffId?: string;
  canOverrideCredit: boolean;
};

function saleRequest(sale: TillSale, checkout: TillCheckout, basket: SavedBasket): TillSalePayload {
  const pickIds = salePickIds(sale.linkedPickIds, sale.pickId);
  const notePrinted = sale.notePrinted.trim();
  const noteInternal = sale.noteInternal.trim();
  return {
    location_id: checkout.locationId,
    basket_id: basket.id,
    basket_version: basket.version,
    ...tillPriceRequest(sale.cart, sale.customerId),
    price_revision: checkout.priceRevision,
    tender: checkout.tender,
    ...(checkout.tender === "statement" ? { due_date: checkout.dueDate } : {}),
    ...(notePrinted ? { note_printed: notePrinted } : {}),
    ...(noteInternal ? { note_internal: noteInternal } : {}),
    ...(checkout.salesStaffId ? { sales_staff_id: checkout.salesStaffId } : {}),
    ...(sale.quoteId ? { quote_id: sale.quoteId } : {}),
    ...(sale.pickId ? { pick_id: sale.pickId } : {}),
    ...(pickIds.length > 0 ? { pick_ids: pickIds } : {}),
    ...(creditOverrideActive(sale, checkout.tender, checkout.canOverrideCredit)
      ? { credit_override: true, credit_override_reason: sale.creditOverrideReason.trim() }
      : {}),
  };
}

export type TillSaleOutcome =
  | { kind: "sold"; result: TillSaleResult }
  /** The server kept its own basket; the 409 usually carries it. */
  | { kind: "basket_conflict"; error: unknown }
  /** Prices moved since the preview: show the message and price again. */
  | { kind: "price_conflict"; message: string }
  /** Customer on hold or over their limit: show the message and offer the override. */
  | { kind: "credit_block"; message: string }
  /** Kits whose parts need a pick first; the kits say why, so no message. */
  | { kind: "kit_requires_pick"; kits: TillKitBlock[] }
  | { kind: "error"; message: string };

function saleFailure(error: unknown): Exclude<TillSaleOutcome, { kind: "sold" }> {
  if (isBasketConflict(error)) return { kind: "basket_conflict", error };
  const message = error instanceof Error ? error.message : "Sale failed.";
  const code = conflictCode(error);
  if (code === "till_price_conflict") return { kind: "price_conflict", message };
  if (code === "customer_credit_blocked") return { kind: "credit_block", message };
  const kits = parseKitRequiresPick(error)?.kits;
  if (kits) return { kind: "kit_requires_pick", kits };
  return { kind: "error", message };
}

/** Save the basket, sell it and say what happened. Never throws. */
export async function completeTillSale(
  ports: {
    /** The basket the server holds once the latest cart is saved (the basket saver's flush). */
    flush: () => Promise<SavedBasket>;
    create: (body: TillSalePayload) => Promise<TillSaleResult>;
  },
  sale: TillSale,
  checkout: TillCheckout,
): Promise<TillSaleOutcome> {
  try {
    const basket = await ports.flush();
    return { kind: "sold", result: await ports.create(saleRequest(sale, checkout, basket)) };
  } catch (error) {
    return saleFailure(error);
  }
}

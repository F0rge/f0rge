import {
  ApiError, type HeldSale, type HeldSaleCreate, type HeldSaleResume, type PickDocument, type TillBasket,
  type TillBasketUpdate,
} from "./api";
import type { TillCartSnapshot } from "./till-kit-pick";

export type PendingHeldOperation =
  | { kind: "hold"; request: HeldSaleCreate }
  | {
      kind: "resume"; id: string; reference: string; request: HeldSaleResume; destination: TillCartSnapshot;
      startedAt?: number;
    };

/** Basket contents in the shape shared by held sales and the server basket. */
export type BasketContents = Omit<TillBasketUpdate, "version" | "operation_id">;

export function cartSnapshot(source: HeldSale | TillBasket): TillCartSnapshot {
  return {
    locationId: source.location_id,
    customerId: source.customer_id ?? "",
    pickId: source.pick_id ?? "",
    linkedPickIds: source.linked_pick_ids,
    note: source.note ?? "",
    notePrinted: source.note_printed ?? "",
    noteInternal: source.note_internal ?? "",
    salesStaffId: source.sales_staff_id ?? "",
    quoteId: source.quote_id ?? "",
    lines: source.lines.map((line) => ({
      skuId: line.sku_id, qty: line.qty, discountPercent: Number(line.discount_percent),
    })),
  };
}

export function basketContents(cart: TillCartSnapshot, picks: PickDocument[] = []): BasketContents {
  const lines = new Set(cart.lines.map((line) => line.skuId));
  const legacyPick = picks.find((pick) => pick.id === cart.pickId);
  const pickId = legacyPick?.kit_sku_id && !lines.has(legacyPick.kit_sku_id) ? "" : cart.pickId;
  return {
    ...(cart.customerId ? { customer_id: cart.customerId } : {}),
    ...(pickId ? { pick_id: pickId } : {}),
    linked_pick_ids: Object.fromEntries(
      Object.entries(cart.linkedPickIds).filter(([skuId]) => lines.has(skuId)),
    ),
    ...(cart.note ? { note: cart.note } : {}),
    ...(cart.notePrinted ? { note_printed: cart.notePrinted } : {}),
    ...(cart.noteInternal ? { note_internal: cart.noteInternal } : {}),
    ...(cart.salesStaffId ? { sales_staff_id: cart.salesStaffId } : {}),
    ...(cart.quoteId ? { quote_id: cart.quoteId } : {}),
    lines: cart.lines.map((line) => ({
      sku_id: line.skuId, qty: line.qty,
      ...(line.discountPercent ? { discount_percent: line.discountPercent } : {}),
    })),
  };
}

export function heldSaleRequest(
  cart: TillCartSnapshot,
  picks: PickDocument[] = [],
): HeldSaleCreate {
  return { id: crypto.randomUUID(), location_id: cart.locationId, ...basketContents(cart, picks) };
}

export function isUncertainHeldResponse(error: unknown): boolean {
  return !(error instanceof ApiError) || error.status === 0 || error.status === 408 ||
    error.status === 429 || error.status === 499 || error.status >= 500;
}

/** Target conflicts are checked after replay. Stay inside the server's 30-day receipt window. */
export function canKeepOriginalBasket(error: unknown, operation: PendingHeldOperation, now = Date.now()): boolean {
  if (operation.kind !== "resume" || operation.startedAt === undefined) return false;
  const age = now - operation.startedAt;
  return age >= 0 && age < 29 * 24 * 60 * 60 * 1000 &&
    error instanceof ApiError && error.status === 409 &&
    Boolean(error.detail && typeof error.detail === "object" &&
      "code" in error.detail && error.detail.code === "held_resume_target_changed");
}

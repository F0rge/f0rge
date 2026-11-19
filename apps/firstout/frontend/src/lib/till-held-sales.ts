import { ApiError, type HeldSale, type HeldSaleCreate, type HeldSaleResume, type PickDocument } from "./api";
import type { TillCartSnapshot } from "./till-kit-pick";

export type PendingHeldOperation =
  | { kind: "hold"; request: HeldSaleCreate }
  | {
      kind: "resume"; id: string; reference: string; request: HeldSaleResume; destination: TillCartSnapshot;
      startedAt?: number;
    };

export type TillSession = { cart: TillCartSnapshot; pending?: PendingHeldOperation };

export function tillSessionKey(teamId: string, userId: string): string {
  return `firstout.till.cart.v2:${JSON.stringify([teamId, userId])}`;
}

export function readTillSession(key: string): TillSession | null {
  const raw = sessionStorage.getItem(key);
  if (!raw) return null;
  const value = JSON.parse(raw) as TillSession | null;
  if (!value?.cart || !Array.isArray(value.cart.lines) || typeof value.cart.locationId !== "string") {
    throw new Error("The saved till cart could not be read.");
  }
  if (value.pending &&
      (!["hold", "resume"].includes(value.pending.kind) ||
       value.pending.request?.location_id !== value.cart.locationId ||
       (value.pending.kind === "resume" &&
        value.pending.destination?.locationId !== value.cart.locationId))) {
    throw new Error("The saved till operation could not be read.");
  }
  return value;
}

export function saveTillSession(key: string, value: TillSession): boolean {
  try {
    sessionStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export function snapshotHeldSale(sale: HeldSale): TillCartSnapshot {
  return {
    locationId: sale.location_id,
    customerId: sale.customer_id ?? "",
    pickId: sale.pick_id ?? "",
    linkedPickIds: sale.linked_pick_ids,
    note: sale.note ?? "",
    held: true,
    lines: sale.lines.map((line) => ({
      skuId: line.sku_id, qty: line.qty, discountPercent: Number(line.discount_percent),
    })),
  };
}

export function heldSaleRequest(
  cart: TillCartSnapshot,
  picks: PickDocument[] = [],
): HeldSaleCreate {
  const lines = new Set(cart.lines.map((line) => line.skuId));
  const legacyPick = picks.find((pick) => pick.id === cart.pickId);
  const pickId = legacyPick?.kit_sku_id && !lines.has(legacyPick.kit_sku_id) ? "" : cart.pickId;
  return {
    id: crypto.randomUUID(),
    location_id: cart.locationId,
    ...(cart.customerId ? { customer_id: cart.customerId } : {}),
    ...(pickId ? { pick_id: pickId } : {}),
    linked_pick_ids: Object.fromEntries(
      Object.entries(cart.linkedPickIds).filter(([skuId]) => lines.has(skuId)),
    ),
    ...(cart.note ? { note: cart.note } : {}),
    lines: cart.lines.map((line) => ({
      sku_id: line.skuId, qty: line.qty,
      ...(line.discountPercent ? { discount_percent: line.discountPercent } : {}),
    })),
  };
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

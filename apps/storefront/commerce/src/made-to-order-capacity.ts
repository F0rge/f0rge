export type MadeToOrderOffer = {
  id: string;
  capacity: number;
  min_lead_time_days: number;
  max_lead_time_days: number;
  expires_at: string;
};

export type FulfillmentPromise = {
  kind: "stocked" | "made_to_order";
  offer_id?: string;
  min_lead_time_days?: number;
  max_lead_time_days?: number;
  estimated_from: string;
  estimated_by: string;
  expires_at?: string;
};

export type CapacityHold = {
  cart_id: string;
  line_item_id: string;
  quantity: number;
  expires_at: string;
  fulfillment_promise: FulfillmentPromise;
};

export type CapacityAllocation = MadeToOrderOffer & {
  source_revision: string;
  holds: Record<string, CapacityHold>;
  committed: Record<string, number>;
};

export type MadeToOrderCapacityState = {
  version: 1;
  current_offer_id: string | null;
  allocations: Record<string, CapacityAllocation>;
};

export type MadeToOrderOfferPresentation = MadeToOrderOffer & { remaining_capacity: number };

export const CAPACITY_STATE_METADATA_KEY = "storefront_made_to_order_capacity";

export function holdKey(cartId: string, lineItemId: string): string {
  return `${cartId}:${lineItemId}`;
}

function record(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown> : null;
}

function validOffer(value: unknown): value is MadeToOrderOffer {
  const offer = record(value);
  return !!offer && typeof offer.id === "string" && offer.id.length > 0 &&
    Number.isSafeInteger(offer.capacity) && Number(offer.capacity) >= 0 &&
    Number.isSafeInteger(offer.min_lead_time_days) && Number(offer.min_lead_time_days) >= 1 &&
    Number.isSafeInteger(offer.max_lead_time_days) && Number(offer.max_lead_time_days) >= Number(offer.min_lead_time_days) &&
    typeof offer.expires_at === "string" && Number.isFinite(Date.parse(offer.expires_at));
}

function emptyState(): MadeToOrderCapacityState {
  return { version: 1, current_offer_id: null, allocations: {} };
}

export function readCapacityState(metadata: Record<string, unknown> | null): MadeToOrderCapacityState {
  const raw = record(metadata?.[CAPACITY_STATE_METADATA_KEY]);
  if (!raw) return emptyState();
  const allocations = record(raw.allocations);
  if (raw.version !== 1 || !allocations ||
    (raw.current_offer_id !== null && typeof raw.current_offer_id !== "string")) {
    throw new Error("invalid_made_to_order_capacity_state");
  }
  const parsed: Record<string, CapacityAllocation> = {};
  for (const [id, value] of Object.entries(allocations)) {
    const allocation = record(value);
    const holds = record(allocation?.holds);
    const committed = record(allocation?.committed);
    if (!validOffer(value) || value.id !== id || !holds || !committed ||
      typeof allocation?.source_revision !== "string") {
      throw new Error("invalid_made_to_order_capacity_allocation");
    }
    const parsedHolds: Record<string, CapacityHold> = {};
    for (const [key, holdValue] of Object.entries(holds)) {
      const hold = record(holdValue);
      const promise = record(hold?.fulfillment_promise);
      if (!hold || typeof hold.cart_id !== "string" || typeof hold.line_item_id !== "string" ||
        !Number.isSafeInteger(hold.quantity) || Number(hold.quantity) < 1 ||
        typeof hold.expires_at !== "string" || !Number.isFinite(Date.parse(hold.expires_at)) ||
        !promise || (promise.kind !== "made_to_order" && promise.kind !== "stocked")) {
        throw new Error("invalid_made_to_order_capacity_hold");
      }
      parsedHolds[key] = holdValue as CapacityHold;
    }
    const parsedCommitted: Record<string, number> = {};
    for (const [key, quantity] of Object.entries(committed)) {
      if (!key || !Number.isSafeInteger(quantity) || Number(quantity) < 1) {
        throw new Error("invalid_made_to_order_capacity_commitment");
      }
      parsedCommitted[key] = Number(quantity);
    }
    parsed[id] = { ...value, source_revision: allocation.source_revision, holds: parsedHolds, committed: parsedCommitted };
  }
  if (raw.current_offer_id !== null && !parsed[String(raw.current_offer_id)]) {
    throw new Error("missing_current_made_to_order_allocation");
  }
  return { version: 1, current_offer_id: raw.current_offer_id as string | null, allocations: parsed };
}

/**
 * Sync applies the newest source row but keeps local holds and paid units for every
 * offer ID. A delayed acknowledgement or stale catalogue row cannot reset an allocation.
 */
export function mergeCapacityState(
  metadata: Record<string, unknown> | null,
  offer: MadeToOrderOffer | null,
  sourceRevision: string,
): MadeToOrderCapacityState {
  const state = readCapacityState(metadata);
  const appliedRevision = metadata?.source_revision;
  if (typeof appliedRevision === "string" && sourceRevision < appliedRevision) return state;
  if (!offer) return { ...state, current_offer_id: null };
  if (!validOffer(offer)) throw new Error("invalid_made_to_order_offer");
  if (typeof appliedRevision === "string" && sourceRevision === appliedRevision &&
    Object.keys(state.allocations).length > 0 && !state.allocations[offer.id]) return state;
  const previous = state.allocations[offer.id];
  if (previous && sourceRevision < previous.source_revision) return state;
  const allocation: CapacityAllocation = {
    ...offer,
    source_revision: sourceRevision,
    holds: previous?.holds || {},
    committed: previous?.committed || {},
  };
  return {
    version: 1,
    current_offer_id: offer.id,
    allocations: { ...state.allocations, [offer.id]: allocation },
  };
}

export function availableCapacity(allocation: CapacityAllocation, nowMs: number): number {
  const held = Object.values(allocation.holds)
    .filter((hold) => Date.parse(hold.expires_at) > nowMs)
    .reduce((total, hold) => total + hold.quantity, 0);
  const committed = Object.values(allocation.committed).reduce((total, quantity) => total + quantity, 0);
  return Math.max(0, allocation.capacity - held - committed);
}

export function offerPresentation(
  state: MadeToOrderCapacityState,
  nowMs: number,
): MadeToOrderOfferPresentation | null {
  const id = state.current_offer_id;
  if (!id) return null;
  const allocation = state.allocations[id];
  if (!allocation || Date.parse(allocation.expires_at) <= nowMs) return null;
  return {
    id: allocation.id,
    capacity: allocation.capacity,
    min_lead_time_days: allocation.min_lead_time_days,
    max_lead_time_days: allocation.max_lead_time_days,
    expires_at: allocation.expires_at,
    remaining_capacity: availableCapacity(allocation, nowMs),
  };
}

function addDays(date: Date, days: number): string {
  const result = new Date(date);
  result.setUTCDate(result.getUTCDate() + days);
  return result.toISOString().slice(0, 10);
}

export function madeToOrderPromise(offer: MadeToOrderOffer, acceptedAt: Date): FulfillmentPromise {
  return {
    kind: "made_to_order",
    offer_id: offer.id,
    min_lead_time_days: offer.min_lead_time_days,
    max_lead_time_days: offer.max_lead_time_days,
    estimated_from: addDays(acceptedAt, offer.min_lead_time_days),
    estimated_by: addDays(acceptedAt, offer.max_lead_time_days),
    expires_at: offer.expires_at,
  };
}

export function stockedPromise(acceptedAt: Date): FulfillmentPromise {
  const date = acceptedAt.toISOString().slice(0, 10);
  return { kind: "stocked", estimated_from: date, estimated_by: date };
}

export function reserveCapacity(
  state: MadeToOrderCapacityState,
  offerId: string,
  cartId: string,
  lineItemId: string,
  quantity: number,
  holdExpiresAt: string,
  acceptedAt: Date,
): MadeToOrderCapacityState {
  const allocation = state.allocations[offerId];
  const nowMs = acceptedAt.getTime();
  if (!allocation || state.current_offer_id !== offerId || Date.parse(allocation.expires_at) <= nowMs ||
    Date.parse(holdExpiresAt) <= nowMs || !Number.isSafeInteger(quantity) || quantity < 1) {
    throw new Error("made_to_order_offer_unavailable");
  }
  const key = holdKey(cartId, lineItemId);
  const existing = allocation.holds[key];
  const withoutExisting = {
    ...allocation,
    holds: Object.fromEntries(Object.entries(allocation.holds).filter(([holdId]) => holdId !== key)),
  };
  if (existing && existing.quantity === quantity && Date.parse(existing.expires_at) > nowMs) {
    return state;
  }
  if (availableCapacity(withoutExisting, nowMs) < quantity) throw new Error("made_to_order_capacity_exhausted");
  const hold: CapacityHold = {
    cart_id: cartId,
    line_item_id: lineItemId,
    quantity,
    expires_at: holdExpiresAt,
    fulfillment_promise: madeToOrderPromise(allocation, acceptedAt),
  };
  return {
    ...state,
    allocations: { ...state.allocations, [offerId]: { ...allocation, holds: { ...withoutExisting.holds, [key]: hold } } },
  };
}

export function releaseCapacityHold(
  state: MadeToOrderCapacityState,
  cartId: string,
  lineItemId: string,
): { state: MadeToOrderCapacityState; released: boolean } {
  const key = holdKey(cartId, lineItemId);
  let released = false;
  const allocations = Object.fromEntries(Object.entries(state.allocations).map(([id, allocation]) => {
    if (!allocation.holds[key]) return [id, allocation];
    released = true;
    const { [key]: _removed, ...holds } = allocation.holds;
    return [id, { ...allocation, holds }];
  }));
  return { state: { ...state, allocations }, released };
}

export function consumeCapacity(
  state: MadeToOrderCapacityState,
  offerId: string,
  cartId: string,
  lineItemId: string,
  commitmentId: string,
  quantity: number,
  nowMs = Date.now(),
): MadeToOrderCapacityState {
  const allocation = state.allocations[offerId];
  if (!allocation) throw new Error("made_to_order_allocation_missing");
  const previous = allocation.committed[commitmentId];
  if (previous !== undefined) {
    if (previous !== quantity) throw new Error("made_to_order_commitment_conflict");
    return state;
  }
  const key = holdKey(cartId, lineItemId);
  const hold = allocation.holds[key];
  if (!hold || hold.quantity !== quantity) throw new Error("made_to_order_capacity_hold_missing");
  if (Date.parse(allocation.expires_at) <= nowMs || Date.parse(hold.expires_at) <= nowMs) {
    throw new Error("made_to_order_capacity_hold_expired");
  }
  const { [key]: _removed, ...holds } = allocation.holds;
  return {
    ...state,
    allocations: { ...state.allocations, [offerId]: {
      ...allocation, holds, committed: { ...allocation.committed, [commitmentId]: quantity },
    } },
  };
}

/** Release one durable paid-order commitment after an accepted cancellation. */
export function releaseCapacityCommitment(
  state: MadeToOrderCapacityState,
  offerId: string,
  commitmentId: string,
): { state: MadeToOrderCapacityState; released: number } {
  const allocation = state.allocations[offerId];
  if (!allocation) return { state, released: 0 };
  const quantity = allocation.committed[commitmentId];
  if (quantity === undefined) return { state, released: 0 };
  const { [commitmentId]: _removed, ...committed } = allocation.committed;
  return {
    state: { ...state, allocations: { ...state.allocations, [offerId]: { ...allocation, committed } } },
    released: quantity,
  };
}

export function releaseExpiredCapacityHolds(
  state: MadeToOrderCapacityState,
  nowMs: number,
): { state: MadeToOrderCapacityState; released: number } {
  let released = 0;
  const allocations = Object.fromEntries(Object.entries(state.allocations).map(([id, allocation]) => {
    const holds = Object.fromEntries(Object.entries(allocation.holds).filter(([, hold]) => {
      const active = Date.parse(hold.expires_at) > nowMs;
      if (!active) released += 1;
      return active;
    }));
    return [id, { ...allocation, holds }];
  }));
  return { state: { ...state, allocations }, released };
}

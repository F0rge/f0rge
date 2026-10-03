import type { MedusaContainer } from "@medusajs/framework/types";
import { ContainerRegistrationKeys, MedusaError, Modules } from "@medusajs/framework/utils";
import {
  createReservationsWorkflow,
  deleteReservationsWorkflow,
  refreshCartItemsWorkflow,
  updateCartWorkflow,
  updateLineItemInCartWorkflow,
  updateProductVariantsWorkflow,
} from "@medusajs/medusa/core-flows";
import {
  CAPACITY_STATE_METADATA_KEY,
  availableCapacity,
  madeToOrderPromise,
  mergeCapacityState,
  offerPresentation,
  readCapacityState,
  releaseCapacityHold,
  releaseExpiredCapacityHolds,
  reserveCapacity,
  stockedPromise,
  type CapacityHold,
  type FulfillmentPromise,
  type MadeToOrderCapacityState,
} from "./made-to-order-capacity";
import {
  currentOpsCheckoutHealth,
  operationalCheckoutBlock,
} from "./storefront-commerce-exceptions";

type CartLine = { id: string; variant_id: string | null; quantity: number; unit_price: number; metadata?: Record<string, unknown> | null };
type Cart = { id: string; metadata: Record<string, unknown> | null; items: CartLine[] | null; currency_code: string };
type Variant = {
  id: string;
  metadata: Record<string, unknown> | null;
  inventory_items?: { inventory_item_id: string }[];
  prices?: { amount: number; currency_code: string }[];
};
type CapacityHoldReference = { line_item_id: string; offer_id: string; quantity: number };
export type FulfillmentPromiseSummary = {
  version: 1;
  kind: "stocked" | "made_to_order" | "mixed";
  accepted_at: string;
  estimated_from: string;
  estimated_by: string;
};
type HoldMetadata = {
  status: "active" | "review" | "expired" | "cancelled";
  expires_at?: string;
  changes?: string[];
  capacity_holds?: CapacityHoldReference[];
  fulfillment_promise?: FulfillmentPromiseSummary;
};
type Reservation = { id: string; created_by?: string | null; metadata: Record<string, unknown> | null };

const holdCreator = (cartId: string) => `storefront_hold:${cartId}`;
const inventoryLock = "storefront:inventory";

function positiveDuration(name: string, fallback: number): number {
  const value = process.env[name];
  if (!value) return fallback;
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < 1) throw new MedusaError(MedusaError.Types.INVALID_DATA, `${name} must be a positive integer`);
  return parsed;
}

export function holdTtlMs(): number { return positiveDuration("STOREFRONT_HOLD_TTL_SECONDS", 1200) * 1000; }
export function availabilityMaxAgeMs(): number { return positiveDuration("STOREFRONT_AVAILABILITY_MAX_AGE_SECONDS", 300) * 1000; }

function holdMetadata(cart: Cart): HoldMetadata | undefined {
  const value = cart.metadata?.storefront_hold;
  return value && typeof value === "object" ? value as HoldMetadata : undefined;
}

function itemPromise(line: CartLine): FulfillmentPromise | null {
  const value = line.metadata?.fulfillment_promise;
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const promise = value as FulfillmentPromise;
  return promise.kind === "stocked" || promise.kind === "made_to_order" ? promise : null;
}

function currentOffer(variant: Variant, nowMs: number) {
  const state = readCapacityState(variant.metadata);
  const offerId = state.current_offer_id;
  const allocation = offerId ? state.allocations[offerId] : undefined;
  if (!allocation || allocation.capacity < 1 || Date.parse(allocation.expires_at) <= nowMs) return null;
  return { state, offer: allocation };
}

function offerForPromise(variant: Variant, promise: FulfillmentPromise, nowMs: number) {
  if (promise.kind !== "made_to_order" || !promise.offer_id) return null;
  const state = readCapacityState(variant.metadata);
  const allocation = state.allocations[promise.offer_id];
  if (!allocation || Date.parse(allocation.expires_at) <= nowMs) return null;
  return { state, offer: allocation };
}

function sourceQuantity(variant: Variant): number {
  const value = variant.metadata?.source_available_quantity;
  const quantity = typeof value === "number" || typeof value === "string" ? Number(value) : NaN;
  return Number.isSafeInteger(quantity) && quantity >= 0 ? quantity : 0;
}

function fulfillmentSummary(promises: FulfillmentPromise[], acceptedAt: Date): FulfillmentPromiseSummary {
  const kinds = new Set(promises.map((promise) => promise.kind));
  const starts = promises.map((promise) => promise.estimated_from).sort();
  const ends = promises.map((promise) => promise.estimated_by).sort();
  return {
    version: 1,
    kind: kinds.size > 1 ? "mixed" : (promises[0]?.kind || "stocked"),
    accepted_at: acceptedAt.toISOString(),
    estimated_from: starts[starts.length - 1] || acceptedAt.toISOString().slice(0, 10),
    estimated_by: ends[ends.length - 1] || acceptedAt.toISOString().slice(0, 10),
  };
}

async function updateVariantCapacity(
  container: MedusaContainer,
  variant: Variant,
  state: MadeToOrderCapacityState,
  nowMs: number,
): Promise<void> {
  const presentation = offerPresentation(state, nowMs);
  const publicOffer = presentation ? {
    ...presentation,
    observed_at: typeof variant.metadata?.source_observed_at === "string" ? variant.metadata.source_observed_at : null,
  } : null;
  await updateProductVariantsWorkflow(container).run({
    input: { product_variants: [{
      id: variant.id,
      metadata: {
        ...(variant.metadata || {}),
        [CAPACITY_STATE_METADATA_KEY]: state,
        storefront_made_to_order_offer: publicOffer,
      },
    }] },
  });
  variant.metadata = {
    ...(variant.metadata || {}),
    [CAPACITY_STATE_METADATA_KEY]: state,
    storefront_made_to_order_offer: publicOffer,
  };
}

async function updateLinePromise(
  container: MedusaContainer,
  cartId: string,
  line: CartLine,
  promise: FulfillmentPromise | null,
): Promise<void> {
  const metadata = { ...(line.metadata || {}) };
  if (promise) {
    metadata.fulfillment_promise = promise;
    if (promise.kind === "made_to_order") metadata.storefront_capacity_hold_line_id = line.id;
    else delete metadata.storefront_capacity_hold_line_id;
  } else {
    delete metadata.fulfillment_promise;
    delete metadata.storefront_capacity_hold_line_id;
  }
  await updateLineItemInCartWorkflow(container).run({
    input: { cart_id: cartId, item_id: line.id, update: { metadata } },
  });
  line.metadata = metadata;
}

function capacityReferences(hold: Pick<HoldMetadata, "capacity_holds"> | undefined): CapacityHoldReference[] {
  return Array.isArray(hold?.capacity_holds) ? hold.capacity_holds : [];
}

function activePhysicalReservations(cart: Cart, reservations: Reservation[], nowMs: number): Reservation[] {
  return reservations.filter((item) => item.created_by === holdCreator(cart.id) &&
    typeof item.metadata?.expires_at === "string" && Date.parse(item.metadata.expires_at) > nowMs);
}

function activeHoldMatches(
  cart: Cart,
  variants: Variant[],
  reservations: Reservation[],
  nowMs: number,
): boolean {
  const hold = holdMetadata(cart);
  if (hold?.status !== "active" || typeof hold.expires_at !== "string" || Date.parse(hold.expires_at) <= nowMs ||
    !hold.fulfillment_promise) return false;
  const variantById = new Map(variants.map((variant) => [variant.id, variant]));
  const physical = activePhysicalReservations(cart, reservations, nowMs);
  const capacityHolds = capacityReferences(hold);
  const mtoLineIds = new Set<string>();
  for (const line of cart.items || []) {
    const promise = itemPromise(line);
    const variant = line.variant_id ? variantById.get(line.variant_id) : undefined;
    if (!promise || !variant) return false;
    if (promise.kind === "stocked") {
      const reservation = physical.find((item) => item.metadata?.line_item_id === line.id);
      if (!reservation || Number(reservation.metadata?.quantity) !== line.quantity) return false;
      continue;
    }
    const reference = capacityHolds.find((item) => item.line_item_id === line.id && item.quantity === line.quantity && item.offer_id === promise.offer_id);
    const allocation = offerForPromise(variant, promise, nowMs);
    if (!reference || !allocation || !promise.offer_id) return false;
    const key = `${cart.id}:${line.id}`;
    const stored = allocation.state.allocations[promise.offer_id]?.holds[key];
    if (!stored || stored.quantity !== line.quantity || Date.parse(stored.expires_at) <= nowMs ||
      JSON.stringify(stored.fulfillment_promise) !== JSON.stringify(promise)) return false;
    mtoLineIds.add(line.id);
  }
  return capacityHolds.length === mtoLineIds.size;
}

export function checkoutChanges(cart: Cart, variants: Variant[], nowMs: number, maxAgeMs: number): string[] {
  const changes: string[] = [];
  if (!cart.items?.length) return ["Your bag is empty."];
  if (cart.currency_code !== "zar") changes.push("The cart currency is unavailable.");
  const byId = new Map(variants.map((variant) => [variant.id, variant]));
  for (const line of cart.items) {
    if (!Number.isSafeInteger(line.quantity) || line.quantity < 1 || line.quantity > 99) {
      changes.push("Choose a valid quantity for every piece.");
      continue;
    }
    const variant = line.variant_id ? byId.get(line.variant_id) : undefined;
    if (!variant || variant.inventory_items?.length !== 1) {
      changes.push("A piece in your bag is no longer available.");
      continue;
    }
    const observed = variant.metadata?.source_observed_at;
    const observedMs = typeof observed === "string" ? Date.parse(observed) : NaN;
    if (!Number.isFinite(observedMs) || observedMs > nowMs + 60_000 || nowMs - observedMs > maxAgeMs) {
      changes.push("Stock information is temporarily unavailable. Your bag is saved; please try again later.");
    }
    const heldPromise = itemPromise(line);
    if (heldPromise?.kind === "made_to_order") {
      if (!offerForPromise(variant, heldPromise, nowMs)) {
        changes.push("The made-to-order allowance expired. Review availability before paying.");
      }
    } else if (!heldPromise && sourceQuantity(variant) < line.quantity && !currentOffer(variant, nowMs)) {
      changes.push("This piece has no current stock or made-to-order allowance.");
    }
    const price = variant.prices?.find((candidate) => candidate.currency_code === "zar")?.amount;
    if (price == null || !Number.isFinite(price) || Math.round(price * 100) !== Math.round(line.unit_price * 100)) {
      changes.push("A piece's price changed. Review the current total before continuing.");
    }
  }
  return [...new Set(changes)];
}

export function opsCheckoutChanges(nowMs = Date.now()): string[] {
  const health = currentOpsCheckoutHealth();
  const message = operationalCheckoutBlock({
    checkoutAllowed: health.checkoutAllowed,
    lastProjectionAt: health.lastProjectionAt,
    nowMs,
    maxAgeMs: availabilityMaxAgeMs(),
    opsReachable: health.opsReachable,
  });
  return message ? [message] : [];
}

async function retrieveCart(container: MedusaContainer, cartId: string): Promise<Cart> {
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const { data } = await query.graph({
    entity: "cart", fields: ["id", "metadata", "currency_code", "items.id", "items.variant_id", "items.quantity", "items.unit_price", "items.metadata"],
    filters: { id: cartId },
  });
  const cart = data[0] as Cart | undefined;
  if (!cart) throw new MedusaError(MedusaError.Types.NOT_FOUND, "Bag not found");
  return cart;
}

async function retrieveVariants(container: MedusaContainer, cart: Cart): Promise<Variant[]> {
  const ids = (cart.items || []).map((item) => item.variant_id).filter((id): id is string => !!id);
  if (!ids.length) return [];
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const { data } = await query.graph({
    entity: "product_variant", fields: ["id", "metadata", "inventory_items.inventory_item_id", "prices.amount", "prices.currency_code"],
    filters: { id: ids },
  });
  return data as Variant[];
}

async function setHoldMetadata(container: MedusaContainer, cart: Cart, hold: HoldMetadata): Promise<void> {
  const metadata = { ...(cart.metadata || {}), storefront_hold: hold } as Record<string, unknown>;
  if (hold.status === "active" && hold.fulfillment_promise) {
    metadata.storefront_fulfillment_promise = hold.fulfillment_promise;
  } else {
    delete metadata.storefront_fulfillment_promise;
  }
  await updateCartWorkflow(container).run({ input: {
    id: cart.id, metadata,
  } });
  cart.metadata = metadata;
}

async function releaseCapacityForCart(
  container: MedusaContainer,
  cart: Cart,
  variants: Variant[],
  hold: Pick<HoldMetadata, "capacity_holds"> | undefined,
  nowMs: number,
): Promise<number> {
  const byId = new Map(variants.map((variant) => [variant.id, variant]));
  const lineIds = new Set(capacityReferences(hold).map((reference) => reference.line_item_id));
  for (const line of cart.items || []) {
    if (itemPromise(line)?.kind === "made_to_order") lineIds.add(line.id);
  }
  let released = 0;
  for (const line of cart.items || []) {
    if (!lineIds.has(line.id) || !line.variant_id) continue;
    const variant = byId.get(line.variant_id);
    if (!variant) continue;
    const state = readCapacityState(variant.metadata);
    const result = releaseCapacityHold(state, cart.id, line.id);
    if (!result.released) continue;
    released += 1;
    await updateVariantCapacity(container, variant, result.state, nowMs);
  }
  return released;
}

async function clearLinePromises(container: MedusaContainer, cart: Cart): Promise<void> {
  for (const line of cart.items || []) {
    if (line.metadata?.fulfillment_promise || line.metadata?.storefront_capacity_hold_line_id) {
      await updateLinePromise(container, cart.id, line, null);
    }
  }
}

async function cartReservations(container: MedusaContainer, cartId: string): Promise<Reservation[]> {
  const inventory = container.resolve(Modules.INVENTORY);
  return await inventory.listReservationItems({ created_by: holdCreator(cartId) }) as Reservation[];
}

async function releaseReservations(container: MedusaContainer, cartId: string): Promise<number> {
  const reservations = await cartReservations(container, cartId);
  if (reservations.length) {
    await deleteReservationsWorkflow(container).run({ input: { ids: reservations.map((item) => item.id) } });
  }
  return reservations.length;
}

/** Run checkout state changes under the same inventory lock used by temporary holds. */
export async function withCheckoutInventoryLock<T>(container: MedusaContainer, operation: () => Promise<T>): Promise<T> {
  const locking = container.resolve(Modules.LOCKING);
  return await locking.execute(inventoryLock, operation);
}

/** Caller must hold `withCheckoutInventoryLock`; this rechecks the exact server-side hold and price/stock snapshot. */
export async function checkoutHoldForCart(container: MedusaContainer, cartId: string, nowMs = Date.now()): Promise<{
  ready: boolean;
  expires_at?: string;
  changes: string[];
}> {
  const cart = await retrieveCart(container, cartId);
  const existing = await cartReservations(container, cartId);
  const variants = await retrieveVariants(container, cart);
  const changes = [...opsCheckoutChanges(nowMs), ...checkoutChanges(cart, variants, nowMs, availabilityMaxAgeMs())];
  const storedHold = holdMetadata(cart);
  if (!activeHoldMatches(cart, variants, existing, nowMs)) {
    await releaseCapacityForCart(container, cart, variants, storedHold, nowMs);
    if (existing.length) await releaseReservations(container, cartId);
    await clearLinePromises(container, cart);
    const hold: HoldMetadata = { status: "expired", changes: ["Your reservation expired. Review availability and reserve again before paying."] };
    await setHoldMetadata(container, cart, hold);
    return { ready: false, changes: hold.changes || [] };
  }
  if (changes.length) {
    await releaseCapacityForCart(container, cart, variants, storedHold, nowMs);
    await releaseReservations(container, cartId);
    await clearLinePromises(container, cart);
    if (changes.some((change) => change.includes("price changed"))) {
      await refreshCartItemsWorkflow(container).run({ input: { cart_id: cartId, force_refresh: true } });
    }
    const hold: HoldMetadata = { status: "review", changes };
    await setHoldMetadata(container, cart, hold);
    return { ready: false, changes };
  }
  return { ready: true, expires_at: String(storedHold?.expires_at), changes: [] };
}

/** Caller must hold `withCheckoutInventoryLock`; removes temporary holds before Medusa creates order reservations. */
export async function releaseCheckoutHoldWithinLock(container: MedusaContainer, cartId: string): Promise<void> {
  await releaseReservations(container, cartId);
}

export async function startCheckoutHold(container: MedusaContainer, cartId: string, nowMs = Date.now()): Promise<HoldMetadata> {
  const locking = container.resolve(Modules.LOCKING);
  return await locking.execute(inventoryLock, async () => {
    const cart = await retrieveCart(container, cartId);
    const existing = await cartReservations(container, cartId);
    const variants = await retrieveVariants(container, cart);
    const changes = [...opsCheckoutChanges(nowMs), ...checkoutChanges(cart, variants, nowMs, availabilityMaxAgeMs())];
    const oldHold = holdMetadata(cart);
    if (oldHold?.status === "active" && activeHoldMatches(cart, variants, existing, nowMs) && !changes.length) {
      return oldHold;
    }
    await releaseCapacityForCart(container, cart, variants, oldHold, nowMs);
    if (existing.length) await releaseReservations(container, cartId);
    await clearLinePromises(container, cart);
    if (changes.length) {
      if (changes.some((change) => change.includes("price changed"))) {
        await refreshCartItemsWorkflow(container).run({ input: { cart_id: cartId, force_refresh: true } });
      }
      const hold: HoldMetadata = { status: "review", changes };
      await setHoldMetadata(container, cart, hold);
      return hold;
    }

    const byId = new Map(variants.map((variant) => [variant.id, variant]));
    const acceptedAt = new Date(nowMs);
    const baseExpiry = nowMs + holdTtlMs();
    const plans: { line: CartLine; variant: Variant; kind: "stocked" | "made_to_order"; offerId?: string; promise?: FulfillmentPromise }[] = [];
    let holdExpiryMs = baseExpiry;
    for (const line of cart.items || []) {
      const variant = line.variant_id ? byId.get(line.variant_id) : undefined;
      if (!variant) continue;
      if (sourceQuantity(variant) >= line.quantity) {
        plans.push({ line, variant, kind: "stocked", promise: stockedPromise(acceptedAt) });
        continue;
      }
      let current: ReturnType<typeof currentOffer>;
      try { current = currentOffer(variant, nowMs); }
      catch { current = null; }
      if (!current || availableCapacity(current.offer, nowMs) < line.quantity) {
        const hold: HoldMetadata = { status: "review", changes: ["The finite made-to-order allowance is exhausted or expired. Your bag is saved."] };
        await setHoldMetadata(container, cart, hold);
        return hold;
      }
      holdExpiryMs = Math.min(holdExpiryMs, Date.parse(current.offer.expires_at));
      plans.push({ line, variant, kind: "made_to_order", offerId: current.offer.id });
    }
    if (holdExpiryMs <= nowMs) {
      const hold: HoldMetadata = { status: "review", changes: ["The made-to-order allowance expired. Your bag is saved."] };
      await setHoldMetadata(container, cart, hold);
      return hold;
    }
    const expiresAt = new Date(holdExpiryMs).toISOString();
    const capacityRefs: CapacityHoldReference[] = [];
    try {
      for (const plan of plans) {
        if (plan.kind !== "made_to_order" || !plan.offerId) continue;
        const state = readCapacityState(plan.variant.metadata);
        const next = reserveCapacity(state, plan.offerId, cartId, plan.line.id, plan.line.quantity, expiresAt, acceptedAt);
        await updateVariantCapacity(container, plan.variant, next, nowMs);
        const promise = next.allocations[plan.offerId].holds[`${cartId}:${plan.line.id}`].fulfillment_promise;
        plan.promise = promise;
        capacityRefs.push({ line_item_id: plan.line.id, offer_id: plan.offerId, quantity: plan.line.quantity });
      }
    } catch {
      await releaseCapacityForCart(container, cart, variants, { capacity_holds: capacityRefs }, nowMs);
      const hold: HoldMetadata = { status: "review", changes: ["The finite made-to-order allowance is no longer available. Your bag is saved."] };
      await setHoldMetadata(container, cart, hold);
      return hold;
    }

    const query = container.resolve(ContainerRegistrationKeys.QUERY);
    const { data: locations } = await query.graph({ entity: "stock_location", fields: ["id"] });
    const locationId = locations[0]?.id;
    if (plans.some((plan) => plan.kind === "stocked") && !locationId) {
      await releaseCapacityForCart(container, cart, variants, { capacity_holds: capacityRefs }, nowMs);
      throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "Store stock location is missing");
    }
    const reservations = plans.filter((plan) => plan.kind === "stocked").map((plan) => ({
      inventory_item_id: plan.variant.inventory_items![0].inventory_item_id,
      location_id: locationId!,
      quantity: plan.line.quantity,
      allow_backorder: false,
      created_by: holdCreator(cartId),
      metadata: { cart_id: cartId, line_item_id: plan.line.id, quantity: plan.line.quantity, expires_at: expiresAt },
    }));
    try {
      if (reservations.length) await createReservationsWorkflow(container).run({ input: { reservations } });
    } catch {
      await releaseReservations(container, cartId);
      await releaseCapacityForCart(container, cart, variants, { capacity_holds: capacityRefs }, nowMs);
      // A competing checkout or operational stock change can make the final unit unavailable.
      const hold: HoldMetadata = { status: "review", changes: ["A piece is no longer available in the requested quantity. Your bag is saved."] };
      await setHoldMetadata(container, cart, hold);
      return hold;
    }
    const promises: FulfillmentPromise[] = [];
    try {
      for (const plan of plans) {
        const promise = plan.promise || stockedPromise(acceptedAt);
        await updateLinePromise(container, cartId, plan.line, promise);
        promises.push(promise);
      }
      const summary = fulfillmentSummary(promises, acceptedAt);
      const hold: HoldMetadata = {
        status: "active", expires_at: expiresAt, capacity_holds: capacityRefs, fulfillment_promise: summary,
      };
      await setHoldMetadata(container, cart, hold);
      return hold;
    }
    catch (error) {
      await releaseReservations(container, cartId);
      await releaseCapacityForCart(container, cart, variants, { capacity_holds: capacityRefs }, nowMs);
      await clearLinePromises(container, cart);
      throw error;
    }
  });
}

export async function cancelCheckoutHold(container: MedusaContainer, cartId: string): Promise<HoldMetadata> {
  const locking = container.resolve(Modules.LOCKING);
  return await locking.execute(inventoryLock, async () => {
    const cart = await retrieveCart(container, cartId);
    const variants = await retrieveVariants(container, cart);
    await releaseCapacityForCart(container, cart, variants, holdMetadata(cart), Date.now());
    await releaseReservations(container, cartId);
    await clearLinePromises(container, cart);
    const hold: HoldMetadata = { status: "cancelled" };
    await setHoldMetadata(container, cart, hold);
    return hold;
  });
}

export async function expireCheckoutHolds(container: MedusaContainer, nowMs = Date.now()): Promise<number> {
  const locking = container.resolve(Modules.LOCKING);
  return await locking.execute(inventoryLock, async () => {
    const inventory = container.resolve(Modules.INVENTORY);
    const reservations: Reservation[] = [];
    const pageSize = 500;
    for (let skip = 0; ; skip += pageSize) {
      const page = await inventory.listReservationItems({}, { skip, take: pageSize }) as Reservation[];
      reservations.push(...page);
      if (page.length < pageSize) break;
    }
    const expired = reservations.filter((item) => item.created_by?.startsWith("storefront_hold:") &&
      typeof item.metadata?.expires_at === "string" && Date.parse(item.metadata.expires_at) <= nowMs);
    if (expired.length) await deleteReservationsWorkflow(container).run({ input: { ids: expired.map((item) => item.id) } });

    const query = container.resolve(ContainerRegistrationKeys.QUERY);
    const { data: variants } = await query.graph({ entity: "product_variant", fields: ["id", "metadata"] });
    let expiredCapacityHolds = 0;
    for (const candidate of variants as Variant[]) {
      if (!candidate.metadata?.[CAPACITY_STATE_METADATA_KEY]) continue;
      const state = readCapacityState(candidate.metadata);
      const result = releaseExpiredCapacityHolds(state, nowMs);
      if (!result.released) continue;
      expiredCapacityHolds += result.released;
      await updateVariantCapacity(container, candidate, result.state, nowMs);
    }
    return expired.length + expiredCapacityHolds;
  });
}

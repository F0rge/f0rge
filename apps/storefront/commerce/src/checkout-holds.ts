import type { MedusaContainer } from "@medusajs/framework/types";
import { ContainerRegistrationKeys, MedusaError, Modules } from "@medusajs/framework/utils";
import { createReservationsWorkflow, deleteReservationsWorkflow, refreshCartItemsWorkflow, updateCartWorkflow } from "@medusajs/medusa/core-flows";

type CartLine = { id: string; variant_id: string | null; quantity: number; unit_price: number };
type Cart = { id: string; metadata: Record<string, unknown> | null; items: CartLine[] | null; currency_code: string };
type Variant = {
  id: string;
  metadata: Record<string, unknown> | null;
  inventory_items?: { inventory_item_id: string }[];
  prices?: { amount: number; currency_code: string }[];
};
type HoldMetadata = { status: "active" | "review" | "expired" | "cancelled"; expires_at?: string; changes?: string[] };
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
    const price = variant.prices?.find((candidate) => candidate.currency_code === "zar")?.amount;
    if (price == null || !Number.isFinite(price) || Math.round(price * 100) !== Math.round(line.unit_price * 100)) {
      changes.push("A piece's price changed. Review the current total before continuing.");
    }
  }
  return [...new Set(changes)];
}

async function retrieveCart(container: MedusaContainer, cartId: string): Promise<Cart> {
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const { data } = await query.graph({
    entity: "cart", fields: ["id", "metadata", "currency_code", "items.id", "items.variant_id", "items.quantity", "items.unit_price"],
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
  await updateCartWorkflow(container).run({ input: {
    id: cart.id, metadata: { ...(cart.metadata || {}), storefront_hold: hold },
  } });
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

export async function startCheckoutHold(container: MedusaContainer, cartId: string, nowMs = Date.now()): Promise<HoldMetadata> {
  const locking = container.resolve(Modules.LOCKING);
  return await locking.execute(inventoryLock, async () => {
    const cart = await retrieveCart(container, cartId);
    const existing = await cartReservations(container, cartId);
    const active = existing.find((item) => typeof item.metadata?.expires_at === "string" && Date.parse(item.metadata.expires_at) > nowMs);
    if (active) {
      const changes = checkoutChanges(cart, await retrieveVariants(container, cart), nowMs, availabilityMaxAgeMs());
      if (changes.length) {
        await releaseReservations(container, cartId);
        if (changes.some((change) => change.includes("price changed"))) {
          await refreshCartItemsWorkflow(container).run({ input: { cart_id: cartId, force_refresh: true } });
        }
        const hold: HoldMetadata = { status: "review", changes };
        await setHoldMetadata(container, cart, hold);
        return hold;
      }
      const expires = String(active.metadata?.expires_at);
      return { status: "active", expires_at: expires };
    }
    if (existing.length) await releaseReservations(container, cartId);

    const variants = await retrieveVariants(container, cart);
    const changes = checkoutChanges(cart, variants, nowMs, availabilityMaxAgeMs());
    if (changes.length) {
      if (changes.some((change) => change.includes("price changed"))) {
        await refreshCartItemsWorkflow(container).run({ input: { cart_id: cartId, force_refresh: true } });
      }
      const hold: HoldMetadata = { status: "review", changes };
      await setHoldMetadata(container, cart, hold);
      return hold;
    }

    const query = container.resolve(ContainerRegistrationKeys.QUERY);
    const { data: locations } = await query.graph({ entity: "stock_location", fields: ["id"] });
    const locationId = locations[0]?.id;
    if (!locationId) throw new MedusaError(MedusaError.Types.UNEXPECTED_STATE, "Store stock location is missing");
    const byId = new Map(variants.map((variant) => [variant.id, variant]));
    const expiresAt = new Date(nowMs + holdTtlMs()).toISOString();
    const reservations = (cart.items || []).map((line) => ({
      inventory_item_id: byId.get(line.variant_id!)!.inventory_items![0].inventory_item_id,
      location_id: locationId,
      quantity: line.quantity,
      allow_backorder: false,
      created_by: holdCreator(cartId),
      metadata: { cart_id: cartId, line_item_id: line.id, expires_at: expiresAt },
    }));
    try {
      await createReservationsWorkflow(container).run({ input: { reservations } });
    } catch {
      await releaseReservations(container, cartId);
      // A competing checkout or operational stock change can make the final unit unavailable.
      const hold: HoldMetadata = { status: "review", changes: ["A piece is no longer available in the requested quantity. Your bag is saved."] };
      await setHoldMetadata(container, cart, hold);
      return hold;
    }
    const hold: HoldMetadata = { status: "active", expires_at: expiresAt };
    try { await setHoldMetadata(container, cart, hold); }
    catch (error) {
      await releaseReservations(container, cartId);
      throw error;
    }
    return hold;
  });
}

export async function cancelCheckoutHold(container: MedusaContainer, cartId: string): Promise<HoldMetadata> {
  const locking = container.resolve(Modules.LOCKING);
  return await locking.execute(inventoryLock, async () => {
    const cart = await retrieveCart(container, cartId);
    await releaseReservations(container, cartId);
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
    if (!expired.length) return 0;
    await deleteReservationsWorkflow(container).run({ input: { ids: expired.map((item) => item.id) } });
    return expired.length;
  });
}

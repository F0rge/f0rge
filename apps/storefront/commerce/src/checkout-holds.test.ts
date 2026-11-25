import type { MedusaContainer } from "@medusajs/framework/types";
import { ContainerRegistrationKeys, Modules } from "@medusajs/framework/utils";
import { updateCartWorkflow } from "@medusajs/medusa/core-flows";
import { availabilityMaxAgeMs, cancelCheckoutHold, checkoutChanges, holdTtlMs, opsCheckoutChanges } from "./checkout-holds";
import { clearCheckoutShippingWorkflow } from "./storefront-checkout-shipping";
import { recordOpsCheckoutHealth, resetOpsCheckoutHealth } from "./storefront-commerce-exceptions";

jest.mock("@medusajs/medusa/core-flows", () => ({
  ...jest.requireActual("@medusajs/medusa/core-flows"),
  updateCartWorkflow: jest.fn(),
}));
jest.mock("./storefront-checkout-shipping", () => ({ clearCheckoutShippingWorkflow: jest.fn() }));

const now = Date.parse("2026-09-28T10:00:00.000Z");
const cart = {
  id: "cart_1", currency_code: "zar", metadata: null,
  items: [{ id: "cali_1", variant_id: "variant_1", quantity: 1, unit_price: 1200 }],
};
const variant = {
  id: "variant_1", metadata: { source_observed_at: "2026-09-28T09:59:00.000Z", source_available_quantity: 1 },
  inventory_items: [{ inventory_item_id: "iitem_1" }],
  prices: [{ amount: 1200, currency_code: "zar" }],
};

test("checkout accepts recent matching price and rejects stale, missing or changed source data", () => {
  expect(checkoutChanges(cart, [variant], now, 5 * 60_000)).toEqual([]);
  expect(checkoutChanges(cart, [variant], now + 6 * 60_000, 5 * 60_000)).toContain(
    "Stock information is temporarily unavailable. Your bag is saved; please try again later.",
  );
  expect(checkoutChanges(cart, [], now, 5 * 60_000)).toContain("A piece in your bag is no longer available.");
  expect(checkoutChanges(cart, [{ ...variant, prices: [{ amount: 1250, currency_code: "zar" }] }], now, 5 * 60_000)).toContain(
    "A piece's price changed. Review the current total before continuing.",
  );
  expect(checkoutChanges({ ...cart, items: [{ ...cart.items[0], quantity: -1 }] }, [variant], now, 5 * 60_000))
    .toContain("Choose a valid quantity for every piece.");
});

test("checkout accepts more than 99 units of a SKU when physical stock covers the request", () => {
  const manyItems = { ...cart, items: [{ ...cart.items[0], quantity: 105 }] };
  const manyStock = { ...variant, metadata: { ...variant.metadata, source_available_quantity: 105 } };
  expect(checkoutChanges(manyItems, [manyStock], now, 5 * 60_000)).toEqual([]);
  expect(checkoutChanges(manyItems, [variant], now, 5 * 60_000))
    .toContain("This piece has no current stock or made-to-order allowance.");
});

test("staleness and reservation limits use configured durations", () => {
  const previousAge = process.env.STOREFRONT_AVAILABILITY_MAX_AGE_SECONDS;
  const previousTtl = process.env.STOREFRONT_HOLD_TTL_SECONDS;
  try {
    process.env.STOREFRONT_AVAILABILITY_MAX_AGE_SECONDS = "120";
    process.env.STOREFRONT_HOLD_TTL_SECONDS = "30";
    expect(availabilityMaxAgeMs()).toBe(120_000);
    expect(holdTtlMs()).toBe(30_000);
    expect(checkoutChanges(cart, [variant], now + 121_000, availabilityMaxAgeMs())).toContain(
      "Stock information is temporarily unavailable. Your bag is saved; please try again later.",
    );
    process.env.STOREFRONT_HOLD_TTL_SECONDS = "0";
    expect(() => holdTtlMs()).toThrow();
  } finally {
    if (previousAge === undefined) delete process.env.STOREFRONT_AVAILABILITY_MAX_AGE_SECONDS;
    else process.env.STOREFRONT_AVAILABILITY_MAX_AGE_SECONDS = previousAge;
    if (previousTtl === undefined) delete process.env.STOREFRONT_HOLD_TTL_SECONDS;
    else process.env.STOREFRONT_HOLD_TTL_SECONDS = previousTtl;
  }
});

test("operational outage and stale projection block new checkout", () => {
  resetOpsCheckoutHealth();
  expect(opsCheckoutChanges(now)[0]).toMatch(/paid orders are kept/);
  recordOpsCheckoutHealth({
    checkoutAllowed: false,
    opsReachable: false,
    lastProjectionAt: "2026-09-28T09:00:00.000Z",
  });
  expect(opsCheckoutChanges(now)[0]).toMatch(/paid orders are kept/);
  recordOpsCheckoutHealth({
    checkoutAllowed: true,
    opsReachable: true,
    lastProjectionAt: "2026-09-28T09:59:00.000Z",
  });
  expect(opsCheckoutChanges(now)).toEqual([]);
});

function checkoutHoldContainer(metadata: Record<string, unknown>) {
  const shippingMethod = { id: "method_reviewed" };
  const graph = jest.fn(async ({ entity }) => {
    if (entity === "cart") return { data: [{ ...cart, metadata, shipping_methods: [shippingMethod] }] };
    if (entity === "product_variant") return { data: [variant] };
    throw new Error("Unexpected query entity: " + entity);
  });
  const container = {
    resolve: (key: string) => {
      if (key === Modules.LOCKING) return { execute: async (_key: string, operation: () => Promise<unknown>) => operation() };
      if (key === Modules.INVENTORY) return { listReservationItems: async () => [] };
      if (key === ContainerRegistrationKeys.QUERY) return { graph };
      return undefined;
    },
  } as unknown as MedusaContainer;
  const updateCart = jest.fn(async () => ({}));
  const clearShipping = jest.fn(async () => ({}));
  (updateCartWorkflow as unknown as jest.Mock).mockReturnValue({ run: updateCart });
  (clearCheckoutShippingWorkflow as unknown as jest.Mock).mockReturnValue({ run: clearShipping });
  return { container, clearShipping, updateCart, shippingMethod };
}

test("backing out after review removes quoted shipping and detaches the unsubmitted address", async () => {
  const { container, clearShipping, updateCart, shippingMethod } = checkoutHoldContainer({ storefront_hold: { status: "active" } });
  const outcome = await cancelCheckoutHold(container, cart.id);
  expect(outcome).toEqual({ status: "cancelled" });
  expect(clearShipping).toHaveBeenCalledWith({ input: { shipping_method_ids: [shippingMethod.id] } });
  expect(updateCart).toHaveBeenNthCalledWith(1, { input: { id: cart.id, shipping_address: null } });
});

test("backing out after payment preparation does not modify the accepted checkout or its shipping", async () => {
  const hold = { status: "active", expires_at: "2026-10-01T12:00:00.000Z" };
  const { container, clearShipping, updateCart } = checkoutHoldContainer({
    storefront_hold: hold, storefront_confirmation_sha256: "synthetic-digest",
  });
  expect(await cancelCheckoutHold(container, cart.id)).toEqual(hold);
  expect(clearShipping).not.toHaveBeenCalled();
  expect(updateCart).not.toHaveBeenCalled();
});

import { availabilityMaxAgeMs, checkoutChanges, holdTtlMs, opsCheckoutChanges } from "./checkout-holds";
import { recordOpsCheckoutHealth, resetOpsCheckoutHealth } from "./storefront-commerce-exceptions";

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

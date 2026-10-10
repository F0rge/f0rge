import { decorateCartTotals, MathBN } from "@medusajs/framework/utils";
import { buildPayload } from "./storefront-order-handoff";

function nativePaidOrder(quantities: number[], delivery = 0, discount = 0) {
  const order = {
    id: "order-money", created_at: "2026-09-28T12:00:00.000Z", email: "buyer@example.com",
    currency_code: "zar", region: { automatic_taxes: true },
    metadata: { storefront_checkout: { fulfillment_type: delivery ? "delivery" : "collection" } },
    shipping_address: {
      first_name: "Ada", last_name: "Buyer", address_1: "1 Test Street", city: "Johannesburg",
      province: "Gauteng", postal_code: "2000", country_code: "za", phone: "+27110000000",
    },
    items: quantities.map((quantity, index) => ({
      id: `item-${index}`, title: `Chair ${index}`, quantity, unit_price: 1000,
      is_tax_inclusive: true, tax_lines: [{ rate: 15 }],
      adjustments: discount ? [{ id: `discount-${index}`, amount: discount }] : [],
      variant: { sku: `SKU-${index}`, metadata: { source_sku_id: `00000000-0000-0000-0000-00000000000${index + 1}` } },
    })),
    shipping_methods: [{ id: "shipping-money", amount: delivery, is_tax_inclusive: true, tax_lines: [{ rate: 15 }] }],
  };
  const decorated = decorateCartTotals(order, { includeTaxes: true });
  return {
    ...order, ...decorated,
    payment_collections: [{ payments: [{
      id: "payment-money", provider_id: "peach", amount: decorated.total,
      currency_code: "zar", captured_at: order.created_at, data: {},
    }] }],
  };
}

const previousCompanyId = process.env.FIRSTOUT_OPS_COMPANY_ID;
beforeAll(() => { process.env.FIRSTOUT_OPS_COMPANY_ID = "00000000-0000-0000-0000-000000000001"; });

afterAll(() => {
  if (previousCompanyId === undefined) delete process.env.FIRSTOUT_OPS_COMPANY_ID;
  else process.env.FIRSTOUT_OPS_COMPANY_ID = previousCompanyId;
});

test("hands off a captured multi-quantity line with an explicit per-unit cent allocation", () => {
  const snapshot = buildPayload(nativePaidOrder([2]));
  expect(snapshot.lines).toMatchObject([{
    external_line_id: "item-0", quantity: 2, unit_ex_minor_zar: 86956,
    unit_ex_remainder_minor_zar: 1, ex_minor_zar: 173913, vat_minor_zar: 26087,
    total_minor_zar: 200000,
  }]);
  expect(snapshot.totals).toMatchObject({ total_minor_zar: 200000, tax_minor_zar: 26087 });
});

test.each([[0], [185.49]])("keeps aggregate VAT and gross totals for separate items and delivery %s", (delivery) => {
  const order = nativePaidOrder([1, 1], delivery);
  const snapshot = buildPayload(order);
  expect(snapshot.lines.map((line) => line.total_minor_zar)).toEqual([100000, 100000]);
  expect(snapshot.lines.map((line) => line.vat_minor_zar)).toEqual([13044, 13043]);
  expect(snapshot.totals.total_minor_zar).toBe(200000 + Math.round(delivery * 100));
  expect(snapshot.totals.tax_minor_zar).toBe(MathBN.mult(order.tax_total, 100).decimalPlaces(0, 4).toNumber());
  expect(snapshot.lines.reduce((sum, line) => sum + line.vat_minor_zar, 0) + snapshot.totals.delivery_tax_minor_zar)
    .toBe(snapshot.totals.tax_minor_zar);
  expect(snapshot.totals.subtotal_ex_minor_zar + snapshot.totals.tax_minor_zar + snapshot.totals.delivery_ex_minor_zar)
    .toBe(snapshot.payment.amount_minor_zar);
  expect(snapshot.fulfillment.fee_total_minor_zar).toBe(Math.round(delivery * 100));
  expect(buildPayload({ ...order, items: [...order.items].reverse() }).lines)
    .toEqual([...snapshot.lines].reverse());
});

test("rejects paid snapshots whose item or payment amounts disagree with the order", () => {
  const order = nativePaidOrder([1]);
  expect(() => buildPayload({ ...order, total: 999 })).toThrow("order_total_mismatch");
  expect(() => buildPayload({ ...order, payment_collections: [{ payments: [{
    ...order.payment_collections[0].payments[0], amount: 999,
  }] }] })).toThrow("payment_amount_mismatch");
});


test("apportions fractional discount gross cents without changing captured payment", () => {
  const order = nativePaidOrder([1, 1], 0, 0.005);
  const snapshot = buildPayload(order);
  expect(snapshot.lines.map((line) => line.total_minor_zar)).toEqual([100000, 99999]);
  expect(snapshot.totals.total_minor_zar).toBe(199999);
  expect(snapshot.lines.reduce((sum, line) => sum + line.total_minor_zar, 0)).toBe(snapshot.payment.amount_minor_zar);
});

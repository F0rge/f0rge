import { storefrontOrderHistory } from "./storefront-order-history";

test("keeps the captured storefront totals after native refund credit lines change the Medusa total", () => {
  const history = storefrontOrderHistory({
    id: "order-history-test",
    subtotal: 0,
    shipping_total: 0,
    tax_total: 0,
    total: 0,
    items: [{ id: "item-1", total: 0 }],
    metadata: {
      storefront_handoff_outbox: {
        status: "imported",
        payload: {
          external_order_id: "order-history-test",
          currency_code: "ZAR",
          totals: {
            subtotal_ex_minor_zar: 100000,
            tax_minor_zar: 18000,
            delivery_ex_minor_zar: 20000,
            delivery_total_minor_zar: 23000,
            total_minor_zar: 138000,
          },
          payment: { amount_minor_zar: 138000, currency_code: "ZAR", captured_at: "2026-10-01T12:00:00.000Z" },
          lines: [{ external_line_id: "item-1", total_minor_zar: 115000 }],
        },
      },
    },
  });

  expect(history).toMatchObject({
    subtotal: 1000,
    shipping_total: 230,
    tax_total: 180,
    total: 1380,
    captured_amount_minor: 138000,
    captured_at: "2026-10-01T12:00:00.000Z",
  });
  expect(history.itemTotals.get("item-1")).toBe(1150);
});

test("falls back to existing values for legacy orders without a captured handoff snapshot", () => {
  const history = storefrontOrderHistory({ subtotal: 100, shipping_total: 20, tax_total: 15, total: 135 });
  expect(history).toMatchObject({ subtotal: 100, shipping_total: 20, tax_total: 15, total: 135 });
  expect(history.itemTotals.size).toBe(0);
  expect(history.captured_amount_minor).toBeNull();
});

test("rejects item projections when the immutable capture currency disagrees", () => {
  const history = storefrontOrderHistory({
    id: "order-history-test",
    subtotal: 80,
    shipping_total: 0,
    tax_total: 20,
    total: 100,
    items: [{ id: "item-1", total: 100 }],
    metadata: {
      storefront_handoff_outbox: {
        status: "imported",
        payload: {
          external_order_id: "order-history-test",
          currency_code: "ZAR",
          totals: { subtotal_ex_minor_zar: 8000, tax_minor_zar: 2000, delivery_ex_minor_zar: 0, delivery_total_minor_zar: 0, total_minor_zar: 10000 },
          payment: { amount_minor_zar: 10000, currency_code: "USD", captured_at: "2026-10-01T12:00:00.000Z" },
          lines: [{ external_line_id: "item-1", total_minor_zar: 10000 }],
        },
      },
    },
  });
  expect(history.total).toBe(100);
  expect(history.itemTotals.size).toBe(0);
  expect(history.captured_amount_minor).toBeNull();
});

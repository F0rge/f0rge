import type { MedusaContainer } from "@medusajs/framework/types";
import { ContainerRegistrationKeys } from "@medusajs/framework/utils";
import { updateProductVariantsWorkflow } from "@medusajs/medusa/core-flows";
import { commitMadeToOrderCapacity } from "./made-to-order-capacity-store";
import { mergeCapacityState, reserveCapacity } from "./made-to-order-capacity";

jest.mock("@medusajs/medusa/core-flows", () => ({
  updateProductVariantsWorkflow: jest.fn(),
}));

test("paid-order conversion uses the stored cart-line ID and order_cart link, then replays idempotently", async () => {
  const offer = {
    id: "bcd2f5d4-237b-43fb-a152-bef10a6a3eaa",
    capacity: 2,
    min_lead_time_days: 28,
    max_lead_time_days: 42,
    expires_at: "2026-10-15T12:00:00.000Z",
  };
  const firstHold = reserveCapacity(
    mergeCapacityState(null, offer, "2026-09-28T11:00:00.000000Z"),
    offer.id,
    "cart-test",
    "cart-line-expected",
    1,
    "2026-09-28T12:20:00.000Z",
    new Date("2026-09-28T12:00:00.000Z"),
  );
  const state = reserveCapacity(
    firstHold,
    offer.id,
    "cart-test",
    "cart-line-second",
    1,
    "2026-09-28T12:20:00.000Z",
    new Date("2026-09-28T12:00:00.000Z"),
  );
  const variant = {
    id: "variant-test",
    sku: "SKU-MTO",
    metadata: {
      source_sku_id: "source-sku-test",
      source_observed_at: "2026-09-28T11:59:00.000Z",
      storefront_made_to_order_capacity: state,
    },
  };
  const order = {
    id: "order-test",
    items: [
      {
        id: "order-line-different-id",
        quantity: 1,
        metadata: {
          fulfillment_promise: { kind: "made_to_order", offer_id: offer.id },
          storefront_capacity_hold_line_id: "cart-line-expected",
        },
        variant,
      },
      {
        id: "order-line-second",
        quantity: 1,
        metadata: {
          fulfillment_promise: { kind: "made_to_order", offer_id: offer.id },
          storefront_capacity_hold_line_id: "cart-line-second",
        },
        variant,
      },
    ],
  };
  const graph = jest.fn(async ({ entity }: { entity: string }) => {
    if (entity === "order") return { data: [order] };
    if (entity === "order_cart") return { data: [{ cart_id: "cart-test" }] };
    throw new Error(`unexpected query graph entity: ${entity}`);
  });
  const query = { graph };
  const run = jest.fn(async ({ input }: { input: { product_variants: { id: string; metadata: Record<string, unknown> }[] } }) => {
    variant.metadata = input.product_variants[0].metadata as typeof variant.metadata;
    return { result: [] };
  });
  (updateProductVariantsWorkflow as unknown as jest.Mock).mockReturnValue({ run });
  const container = {
    resolve: jest.fn((key: string) => {
      expect(key).toBe(ContainerRegistrationKeys.QUERY);
      return query;
    }),
  } as unknown as MedusaContainer;

  await commitMadeToOrderCapacity(container, "order-test", Date.parse("2026-09-28T12:01:00.000Z"));
  expect(graph).toHaveBeenCalledWith(expect.objectContaining({ entity: "order_cart", fields: ["cart_id"], filters: { order_id: "order-test" } }));
  expect(graph).toHaveBeenCalledWith(expect.objectContaining({
    entity: "order",
    fields: expect.arrayContaining(["items.metadata", "items.detail.quantity", "items.variant.id", "items.variant.metadata"]),
  }));
  expect(run).toHaveBeenCalledTimes(2);
  const savedState = variant.metadata.storefront_made_to_order_capacity as ReturnType<typeof mergeCapacityState>;
  expect(savedState.allocations[offer.id].committed).toEqual({
    "storefront:order-test:order-line-different-id": 1,
    "storefront:order-test:order-line-second": 1,
  });
  expect(savedState.allocations[offer.id].holds).toEqual({});

  await commitMadeToOrderCapacity(container, "order-test", Date.parse("2026-09-28T12:02:00.000Z"));
  expect(run).toHaveBeenCalledTimes(2);
});

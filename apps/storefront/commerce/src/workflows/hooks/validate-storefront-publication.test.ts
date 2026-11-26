import type { MedusaContainer } from "@medusajs/framework/types";
import { ContainerRegistrationKeys, Modules, ProductStatus } from "@medusajs/framework/utils";

type Hook = (input: Record<string, unknown>, context: { container: MedusaContainer }) => Promise<void>;
const mockHooks: Record<string, Hook> = {};
jest.mock("@medusajs/medusa/core-flows", () => {
  const flow = (name: string) => ({ hooks: new Proxy({}, { get: () => (fn: Hook) => { mockHooks[name] = fn; } }) });
  return {
    addToCartWorkflow: flow("add"), updateLineItemInCartWorkflow: flow("update"), completeCartWorkflow: flow("complete"),
    createProductsWorkflow: flow("create"), updateProductsWorkflow: flow("updateProducts"),
  };
});
// Registered after mockHooks exists; an import would be hoisted above it.
// eslint-disable-next-line @typescript-eslint/no-require-imports
require("./validate-storefront-publication");
const hooks = mockHooks;

const pairVariant = {
  id: "variant_pair", sku: "CHAIR-OAK", options: [{ option: { title: "Item" }, value: "Standard" }],
  prices: [{ amount: 2450, currency_code: "zar" }],
  metadata: { source_sku_id: "e4653558-60c7-4be7-a416-76fc2c055b8f", source_price_includes_tax: true, source_available_quantity: 6, sell_multiple: 2, min_quantity: 2 },
  product: { id: "prod_chair", external_id: "firstout-chair", title: "Oslo chair", status: ProductStatus.PUBLISHED, options: [{ title: "Item" }], sales_channels: [{ id: "sc_1" }] },
};
const existingLines = [{ id: "cali_1", variant_id: pairVariant.id, quantity: 2 }];
const container = { resolve: (key: string) => ({
  [ContainerRegistrationKeys.QUERY]: { graph: async () => ({ data: [pairVariant] }) },
  [Modules.CART]: { listLineItems: async () => existingLines },
})[key] } as unknown as MedusaContainer;
const cart = { id: "cart_1", sales_channel_id: "sc_1", items: existingLines };

test("adding counts the lines already in the bag", async () => {
  await expect(hooks.add({ input: { items: [{ variant_id: pairVariant.id, quantity: 2 }] }, cart }, { container })).resolves.toBeUndefined();
  await expect(hooks.add({ input: { items: [{ variant_id: pairVariant.id, quantity: 1 }] }, cart }, { container }))
    .rejects.toThrow("This piece is sold in sets of 2.");
});

test("updating checks the replaced total, and a delete is always allowed", async () => {
  const update = (quantity: number | null) => hooks.update({ input: { item_id: "cali_1", update: { quantity } }, cart }, { container });
  await expect(update(4)).resolves.toBeUndefined();
  await expect(update(3)).rejects.toThrow("This piece is sold in sets of 2.");
  await expect(update(0)).resolves.toBeUndefined();
  await expect(update(null)).resolves.toBeUndefined();
});

test("completion does not refuse an off-rule bag after payment", async () => {
  const offRule = { ...cart, items: [{ ...existingLines[0], quantity: 3 }] };
  await expect(hooks.complete({ cart: offRule }, { container })).resolves.toBeUndefined();
});

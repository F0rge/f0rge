import type { CartLineItemDTO, ICartModuleService } from "@medusajs/framework/types";
import { Modules } from "@medusajs/framework/utils";
import { addToCartWorkflow, completeCartWorkflow, createProductsWorkflow, updateLineItemInCartWorkflow, updateProductsWorkflow } from "@medusajs/medusa/core-flows";
import { assertPublishedProductComplete, assertVariantsPurchasable, basketVariantTotals } from "../../publication";

addToCartWorkflow.hooks.validate(async ({ input, cart }, { container }) => {
  const incoming = input.items || [];
  const ids = new Set(incoming.flatMap((item) => item.variant_id ? [item.variant_id] : []));
  if (!ids.size) return;
  const carts = container.resolve<ICartModuleService>(Modules.CART);
  const existing = await carts.listLineItems({ cart_id: cart.id, variant_id: [...ids] });
  const totals = basketVariantTotals([...existing, ...incoming], ids);
  await assertVariantsPurchasable(container, [...ids], cart.sales_channel_id, totals);
});

updateLineItemInCartWorkflow.hooks.validate(async ({ input, cart }, { container }) => {
  const quantity = input.update.quantity;
  if (quantity == null || Number(quantity) === 0) return;
  const items: Pick<CartLineItemDTO, "id" | "variant_id" | "quantity">[] = cart.items || [];
  const id = items.find((item) => item.id === input.item_id)?.variant_id;
  if (!id) return;
  const totals = basketVariantTotals(items.map((item) => item.id === input.item_id ? { ...item, quantity } : item), new Set([id]));
  await assertVariantsPurchasable(container, [id], cart.sales_channel_id, totals);
});

completeCartWorkflow.hooks.validate(async ({ cart }, { container }) => {
  const items: Pick<CartLineItemDTO, "variant_id">[] = cart.items || [];
  const ids = items.map((item) => item.variant_id).filter((id): id is string => !!id);
  await assertVariantsPurchasable(container, ids, cart.sales_channel_id);
});

createProductsWorkflow.hooks.productsCreated(async ({ products }, { container }) => {
  for (const product of products) await assertPublishedProductComplete(container, product.id);
});

updateProductsWorkflow.hooks.productsUpdated(async ({ products }, { container }) => {
  for (const product of products) await assertPublishedProductComplete(container, product.id);
});

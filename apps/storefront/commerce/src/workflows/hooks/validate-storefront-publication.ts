import { addToCartWorkflow, completeCartWorkflow, createProductsWorkflow, updateProductsWorkflow } from "@medusajs/medusa/core-flows";
import { assertPublishedProductComplete, assertVariantsPurchasable } from "../../publication";

addToCartWorkflow.hooks.validate(async ({ input, cart }, { container }) => {
  const ids = (input.items || []).map((item) => item.variant_id).filter((id): id is string => !!id);
  await assertVariantsPurchasable(container, ids, cart.sales_channel_id);
});

completeCartWorkflow.hooks.validate(async ({ cart }, { container }) => {
  const ids = (cart.items || []).map((item) => item.variant_id).filter((id): id is string => !!id);
  await assertVariantsPurchasable(container, ids, cart.sales_channel_id);
});

createProductsWorkflow.hooks.productsCreated(async ({ products }, { container }) => {
  for (const product of products) await assertPublishedProductComplete(container, product.id);
});

updateProductsWorkflow.hooks.productsUpdated(async ({ products }, { container }) => {
  for (const product of products) await assertPublishedProductComplete(container, product.id);
});

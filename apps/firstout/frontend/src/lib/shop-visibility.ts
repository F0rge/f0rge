import { updateSku, type Sku } from "./api";
import { canMutateCatalogue, type PermissionHolder } from "./permissions";

export const SHOP_HIDDEN_HELP =
  "Hidden pieces never appear on daskasas.co.za, even with a photo and stock.";

// Same gate as other SKU edits: catalogue.mutate, and the API refuses edits to archived SKUs.
export function canToggleShopVisibility(
  user: PermissionHolder,
  sku: Pick<Sku, "is_archived">,
): boolean {
  return canMutateCatalogue(user) && !sku.is_archived;
}

export function setSkuShopHidden(skuId: string, hidden: boolean): Promise<Sku> {
  return updateSku(skuId, { storefront_hidden: hidden });
}

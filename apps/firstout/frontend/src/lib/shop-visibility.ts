import { updateSku, type Sku } from "./api";

export const SHOP_HIDDEN_HELP =
  "Hidden pieces never appear on daskasas.co.za once automatic publishing is on, even with a photo and stock.";

export function setSkuShopHidden(skuId: string, hidden: boolean): Promise<Sku> {
  return updateSku(skuId, { storefront_hidden: hidden });
}

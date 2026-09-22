import type { PurchaseOrder, Sku } from "./api";

export function isValidCartonCount(value: number | ""): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 1;
}

export function skuCartonCount(sku: Sku | undefined): number {
  const count = sku?.carton_count;
  return typeof count === "number" && count >= 1 ? count : 1;
}

export function expectedCartonsForPo(
  po: PurchaseOrder,
  skus: Sku[],
): { cartons: number; sellableQty: number } {
  const byId = new Map(skus.map((sku) => [sku.id, sku]));
  let cartons = 0;
  let sellableQty = 0;
  for (const line of po.lines) {
    sellableQty += line.qty;
    cartons += line.qty * skuCartonCount(byId.get(line.sku_id));
  }
  return { cartons, sellableQty };
}

export function formatExpectedCartons(po: PurchaseOrder, skus: Sku[]): string {
  const { cartons, sellableQty } = expectedCartonsForPo(po, skus);
  return `Expected cartons: ${cartons} (sellable qty ${sellableQty})`;
}

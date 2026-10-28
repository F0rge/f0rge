import { listSupplierPrices, type Sku } from "@/lib/api";

/** Fabric / finish shown on a PO line. The catalogue placeholder "-" stays hidden. */
export function displayFabric(fabric: string | null | undefined): string | null {
  const cleaned = (fabric ?? "").trim();
  if (!cleaned || cleaned === "-") {
    return null;
  }
  return cleaned;
}

/**
 * Factory model code for this supplier.
 * The per-supplier code wins when the factory has its own model code on file.
 * Otherwise use the single supplier ref stored on the SKU.
 */
export function manufacturerCode(
  supplierSku: string | null | undefined,
  supplierRef: string | null | undefined,
): string {
  const fromSupplier = (supplierSku ?? "").trim();
  if (fromSupplier) {
    return fromSupplier;
  }
  return (supplierRef ?? "").trim();
}

/** New-PO form: a code the user typed stays; an untouched field takes the factory code. */
export function supplierCodeAfterSkuPick(args: {
  current: string;
  touched: boolean;
  manufacturerCode: string;
}): string {
  if (args.touched) {
    return args.current;
  }
  return args.manufacturerCode;
}

/** Pending-PO edit: only fill a blank box. A code already on the line stays. */
export function supplierCodeWhenBlank(current: string, nextManufacturerCode: string): string {
  if (current.trim()) {
    return current;
  }
  return nextManufacturerCode;
}

export async function lookupManufacturerCode(supplierId: string, sku: Sku): Promise<string> {
  if (!supplierId) {
    return manufacturerCode(null, sku.supplier_ref);
  }
  try {
    const page = await listSupplierPrices(
      { limit: 5 },
      { supplier_id: supplierId, sku_id: sku.id },
    );
    const match = page.items.find(
      (row) => row.sku_id === sku.id && row.supplier_id === supplierId,
    );
    return manufacturerCode(match?.supplier_sku, sku.supplier_ref);
  } catch {
    return manufacturerCode(null, sku.supplier_ref);
  }
}

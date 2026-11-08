import { ApiError, listSupplierPrices, type Sku } from "@/lib/api";

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

export async function lookupManufacturerCode(supplierId: string, sku: Pick<Sku, "id" | "supplier_ref">): Promise<string> {
  if (!supplierId) {
    return manufacturerCode(null, sku.supplier_ref);
  }
  const page = await listSupplierPrices(
    { limit: 5 },
    { supplier_id: supplierId, sku_id: sku.id },
  );
  const match = page.items.find(
    (row) => row.sku_id === sku.id && row.supplier_id === supplierId,
  );
  return manufacturerCode(match?.supplier_sku, sku.supplier_ref);
}

export interface SupplierCodeLine {
  key: string;
  sku_id: string;
  supplier_code: string;
  supplierCodeTouched: boolean;
  supplierCodeLookup?: {
    supplierId: string;
    skuId: string;
    status: "loading" | "error";
    error?: string;
  };
}

type UpdateLines<T extends SupplierCodeLine> = (update: (lines: T[]) => T[]) => void;

/** Changing selection invalidates any old prefill; deliberate manual codes stay. */
export function changeSupplierCodeSku<T extends SupplierCodeLine>(line: T, skuId: string): T {
  return {
    ...line,
    sku_id: skuId,
    supplier_code: line.supplierCodeTouched ? line.supplier_code : "",
    supplierCodeLookup: undefined,
  };
}

export function editSupplierCode<T extends SupplierCodeLine>(line: T, code: string): T {
  return { ...line, supplier_code: code, supplierCodeTouched: true, supplierCodeLookup: undefined };
}

function lookupError(reason: unknown): string {
  if (reason instanceof ApiError && reason.status === 401) return "Sign in again to check the supplier code.";
  if (reason instanceof ApiError && reason.status === 403) return "Ask an owner to check this supplier code, or enter it yourself.";
  return "Couldn't check the supplier code. Retry or enter it yourself.";
}

/** Shared by new PO rows and pending-order rows, including initial blank prefill. */
export async function prefillSupplierCode<T extends SupplierCodeLine>(
  updateLines: UpdateLines<T>, key: string, supplierId: string,
  sku: Pick<Sku, "id" | "supplier_ref">,
): Promise<void> {
  const request = { supplierId, skuId: sku.id, status: "loading" as const };
  const eligible = (line: T) => line.key === key && line.sku_id === sku.id && !line.supplierCodeTouched;
  updateLines((lines) => lines.map((line) => eligible(line)
    ? { ...line, supplier_code: "", supplierCodeLookup: request } : line));
  // Each row owns its request. A supplier/SKU change or retry installs a new
  // object, so even A → B → A cannot accept an earlier completion.
  const currentRequest = (line: T) => eligible(line) && line.supplierCodeLookup === request;
  try {
    const code = await lookupManufacturerCode(supplierId, sku);
    updateLines((lines) => lines.map((line) => currentRequest(line)
      ? { ...line, supplier_code: code, supplierCodeLookup: undefined } : line));
  } catch (reason) {
    updateLines((lines) => lines.map((line) => currentRequest(line)
      ? { ...line, supplierCodeLookup: { ...request, status: "error", error: lookupError(reason) } } : line));
  }
}

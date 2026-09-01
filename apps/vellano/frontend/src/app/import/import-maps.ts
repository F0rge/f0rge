export const INVENTORY_FIELDS = [
  { key: "our_ref", label: "SKU", required: true },
  { key: "name", label: "Name", required: true },
  { key: "category", label: "Category", required: true },
  { key: "retail_inc_vat", label: "Retail Price", required: true },
  { key: "barcode", label: "Barcode", required: false },
  { key: "cost_zar", label: "Cost Price", required: false },
] as const;

export const SOH_FIELDS = [
  { key: "our_ref", label: "SKU", required: true },
  { key: "location", label: "Location", required: true },
  { key: "qty", label: "Qty", required: true },
  { key: "unit_cost_zar", label: "Unit Cost", required: false },
] as const;

export type MapField = {
  key: string;
  label: string;
  required: boolean;
};

export const INVENTORY_TEMPLATE = "SKU,Name,Category,Retail Price,Barcode\n";
export const SOH_TEMPLATE = "SKU,Location,Qty,Unit Cost\n";

export function invertAppliedMap(
  applied: Record<string, string>,
  suggested: Record<string, string>,
  headers: string[],
): Record<string, string> {
  const source = Object.keys(applied).length > 0 ? applied : suggested;
  const next: Record<string, string> = {};
  for (const header of headers) {
    next[header] = "";
  }
  for (const [field, header] of Object.entries(source)) {
    if (header && headers.includes(header) && field) {
      next[header] = field;
    }
  }
  return next;
}

/** our_field → CSV header. Omits empty keys; never sends `""` as a header. */
export function toApiColumnMap(headerToField: Record<string, string>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [header, field] of Object.entries(headerToField)) {
    const csvHeader = header.trim();
    const ourField = field.trim();
    if (csvHeader && ourField) {
      out[ourField] = csvHeader;
    }
  }
  return out;
}

export function assignHeaderField(
  prev: Record<string, string>,
  header: string,
  field: string,
): Record<string, string> {
  const next: Record<string, string> = { ...prev, [header]: field };
  if (field) {
    for (const [otherHeader, otherField] of Object.entries(next)) {
      if (otherHeader !== header && otherField === field) {
        next[otherHeader] = "";
      }
    }
  }
  return next;
}

export function downloadCsvTemplate(filename: string, contents: string): void {
  const blob = new Blob([contents], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export function appendColumnMap(formData: FormData, fieldName: string, headerToField: Record<string, string>): void {
  const mapped = toApiColumnMap(headerToField);
  if (Object.keys(mapped).length === 0) {
    return;
  }
  formData.append(fieldName, JSON.stringify(mapped));
}

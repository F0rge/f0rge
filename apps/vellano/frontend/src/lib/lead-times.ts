import type { SkuLeadTimeRow, SupplierLeadTimeRow } from "./api";

export function formatLeadDays(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "—";
  }
  if (Number.isInteger(value)) {
    return String(value);
  }
  return value.toFixed(1);
}

export function formatObservedMedianLine(
  row: Pick<SupplierLeadTimeRow, "median_days" | "n"> | undefined,
): string {
  if (!row) {
    return "—";
  }
  return `Observed median: ${formatLeadDays(row.median_days)} days (n=${row.n})`;
}

export function isWeakLeadTimeSample(n: number): boolean {
  return n < 3;
}

export function skuLeadTimeById(rows: SkuLeadTimeRow[]): Map<string, SkuLeadTimeRow> {
  return new Map(rows.map((row) => [row.sku_id, row]));
}

export function supplierLeadTimeById(rows: SupplierLeadTimeRow[]): Map<string, SupplierLeadTimeRow> {
  return new Map(rows.map((row) => [row.supplier_id, row]));
}

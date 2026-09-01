import type { SkuCriticalityReport } from "./api";

export function formatSharePct(value: number | string | null | undefined): string {
  const numeric = typeof value === "string" ? Number(value) : value;
  if (numeric === null || numeric === undefined || !Number.isFinite(numeric)) {
    return "—";
  }
  const formatted = Number.isInteger(numeric) ? String(numeric) : numeric.toFixed(1);
  return `${formatted}%`;
}

export function buildCriticalitySummary(report: SkuCriticalityReport): string {
  const topShare = formatSharePct(report.top_sku_share_pct);
  return `Top SKU is ${topShare} of sales; ${report.sku_count_for_50pct} SKUs cover 50%; ${report.sku_count_for_80pct} cover 80%.`;
}

export function abcTagType(abcClass: "A" | "B" | "C"): "green" | "blue" | "gray" {
  if (abcClass === "A") {
    return "green";
  }
  if (abcClass === "B") {
    return "blue";
  }
  return "gray";
}

import type { TillTender } from "@/lib/api";

function toCents(value: number): number {
  return Math.round(value * 100);
}

/** Cash must cover the amount being settled. Other tenders are not cash counts. */
export function cashTenderIsShort(
  tender: TillTender,
  amountTendered: number | null,
  totalIncVat: number,
): boolean {
  if (tender !== "cash" || amountTendered === null) {
    return false;
  }
  return toCents(amountTendered) < toCents(totalIncVat);
}

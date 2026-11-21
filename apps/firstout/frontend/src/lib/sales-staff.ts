import type { CommissionReport, CommissionRow } from "./api";
import { formatPriceAmount, formatZarAmount } from "./api";

const LAST_COLLEAGUE_KEY = "firstout.till.salesColleague";

/** The colleague last chosen on this device, so a shared till keeps its default. */
export function rememberedColleague(): string {
  try {
    return window.localStorage.getItem(LAST_COLLEAGUE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function rememberColleague(id: string): void {
  try {
    if (id) window.localStorage.setItem(LAST_COLLEAGUE_KEY, id);
  } catch {
    // Private windows may refuse storage; the till still asks each time.
  }
}

/** Ex-VAT after discount, leaving out lines whose SKU is excluded from commission. */
export function commissionBase(
  lines: { excluded: boolean; exVat: string | number | undefined }[],
): number {
  return lines.reduce((sum, line) => (line.excluded ? sum : sum + Number(line.exVat ?? 0)), 0);
}

export function zar(value: string | number): string {
  return formatZarAmount(formatPriceAmount(Number(value)));
}

/** YYYY-MM for this month and the eleven before it, newest first. */
export function recentMonths(today = new Date()): { value: string; label: string }[] {
  return Array.from({ length: 12 }, (_, back) => {
    const date = new Date(today.getFullYear(), today.getMonth() - back, 1);
    return {
      value: `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`,
      label: date.toLocaleDateString("en-ZA", { month: "long", year: "numeric" }),
    };
  });
}

export const COMMISSION_CSV_HEADERS = [
  "Colleague", "Invoices", "Commissionable excl. VAT", "Excluded excl. VAT",
  "Credit notes", "Net", "Rate %", "Commission",
];

export function commissionCsvRows(report: CommissionReport): string[][] {
  const line = (row: CommissionRow, rate: string) => [
    row.name, String(row.invoice_count), row.commissionable_ex_vat, row.excluded_ex_vat,
    row.credit_deductions, row.net_commissionable, rate, rate ? row.commission : "",
  ];
  return [
    ...report.rows.map((row) => line(row, row.commission_rate)),
    line(report.unattributed, ""),
    [
      "Total", String(report.invoice_count), report.commissionable_ex_vat, report.excluded_ex_vat,
      report.credit_deductions, report.net_commissionable, "", report.commission,
    ],
  ];
}

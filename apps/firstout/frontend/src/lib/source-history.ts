import { formatZarAmount } from "@/lib/api";

type SourceAmountStatus = {
  source_amounts_known: boolean;
  source_currency_known: boolean;
};

/** Source tax and gross amounts can carry four decimals even though new sales use cents. */
export function formatArchiveCurrency(
  value: string | null | undefined,
  currency = "ZAR",
): string {
  if (value === null || value === undefined) return "—";
  const match = /^([+-]?)(\d+)(?:\.(\d+))?$/.exec(value.trim());
  if (!match) return "—";
  // Keep all Numeric(16,4) digits as text; converting a 12-digit whole part to
  // Number can lose the last fraction before it reaches the display formatter.
  const whole = match[2].replace(/^0+(?=\d)/, "");
  const fraction = (match[3] ?? "").replace(/0+$/, "");
  if (fraction.length > 4) return "—";
  const negative = match[1] === "-" && (whole !== "0" || /[1-9]/.test(fraction));
  return `${currency === "ZAR" ? "R" : currency} ${negative ? "-" : ""}${whole}.${fraction.padEnd(2, "0")}`;
}

/** Imported placeholders must never be presented as known money or a guessed currency. */
export function formatSourceAmount(
  value: string | null,
  source: SourceAmountStatus,
  formatKnown: (amount: string) => string = formatZarAmount,
): string {
  if (!source.source_amounts_known || value === null) return "Not provided in source";
  if (!source.source_currency_known) return `${value} · Currency not provided in source`;
  return formatKnown(value);
}

/** Report Cost/Total are independent source text, not calculated unit prices. */
export function sourceReportAmountText(value: string | null): string {
  return value ?? "Not provided in source";
}

/** Archive payments and opening balances were omitted, so their placeholders are unknown. */
export function formatSettlementAmount(
  value: string,
  isArchive: boolean,
  formatKnown: (amount: string) => string = formatZarAmount,
): string {
  return isArchive ? "Not imported" : formatKnown(value);
}

import { formatZarAmount } from "@/lib/api";

type SourceAmountStatus = {
  source_amounts_known: boolean;
  source_currency_known: boolean;
};

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

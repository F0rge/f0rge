/**
 * Rand amounts in the browser: display formatting and parsing. Sale documents are
 * priced by the server (Firstout ADR 0001). The browser holds no VAT rate (ADR 0003):
 * callers pass a document's stored `vat_rate`, a preview's, or the team's setting.
 */

/**
 * Round to cents using ROUND_HALF_UP (ties away from zero), as the server's Decimal does.
 * toPrecision(15) drops float noise first: 1739.10 x 1.15 is 1999.9649999999997 in binary,
 * a tie at the cent that must round up to 1999.97.
 */
export function roundHalfUp(value: number, decimals = 2): number {
  const factor = 10 ** decimals;
  const scaled = Number((value * factor).toPrecision(15));
  return (Math.sign(scaled) * Math.round(Math.abs(scaled))) / factor;
}

/** `rate` is a VAT rate as the API sends it, e.g. "0.1500". */
export function exVatToIncVat(ex: number, rate: string): number {
  return roundHalfUp(ex * (1 + Number(rate)), 2);
}

export function incVatToExVat(inc: number, rate: string): number {
  return roundHalfUp(inc / (1 + Number(rate)), 2);
}

/** "0.1500" -> "15%". */
export function vatPercentLabel(rate: string): string {
  return `${roundHalfUp(Number(rate) * 100, 2)}%`;
}

export function formatPriceAmount(value: number): string {
  return value.toFixed(2);
}

export function parsePriceInput(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed)) {
    return null;
  }
  return parsed;
}

export function displayPrice(value: string | null | undefined): string {
  return value ?? "—";
}

export function formatZarAmount(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  return `R ${value}`;
}

export function formatFxGainLoss(value: string): string {
  const amount = Number(value);
  if (!Number.isFinite(amount) || amount === 0) {
    return "R 0.00";
  }
  const prefix = amount > 0 ? "Gain " : "Loss ";
  return `${prefix}R ${Math.abs(amount).toFixed(2)}`;
}

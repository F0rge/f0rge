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

const VAT_SCALE = BigInt(10_000);
const TWO = BigInt(2);

/** Team VAT rates have four decimal places and SKU price inputs are in cents. */
function vatFactor(rate: string): bigint {
  return VAT_SCALE + BigInt(Math.round(Number(rate) * Number(VAT_SCALE)));
}

/** Integer conversion matches Decimal HALF_UP even near a cent at large prices. */
function convertVat(amount: number, numerator: bigint, denominator: bigint): number {
  const cents = Math.round(Math.abs(amount) * 100);
  if (!Number.isSafeInteger(cents)) return Number.NaN;
  const converted = (BigInt(cents) * numerator + denominator / TWO) / denominator;
  return (Math.sign(amount) * Number(converted)) / 100;
}

export function exVatToIncVat(ex: number, rate: string): number {
  return convertVat(ex, vatFactor(rate), VAT_SCALE);
}

export function incVatToExVat(inc: number, rate: string): number {
  return convertVat(inc, VAT_SCALE, vatFactor(rate));
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

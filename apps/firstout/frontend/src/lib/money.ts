/**
 * Rand amounts in the browser: display formatting and the client-side VAT
 * preview. Moved unchanged from the HTTP client; the server's totals win.
 */

const VAT_MULTIPLIER = 1.15;

/** Round to cents using ROUND_HALF_UP (ties away from zero). */
export function roundHalfUp(value: number, decimals = 2): number {
  const factor = 10 ** decimals;
  const scaled = value * factor;
  return (Math.sign(scaled) * Math.round(Math.abs(scaled))) / factor;
}

export function exVatToIncVat(ex: number): number {
  return roundHalfUp(ex * VAT_MULTIPLIER, 2);
}

export function incVatToExVat(inc: number): number {
  return roundHalfUp(inc / VAT_MULTIPLIER, 2);
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

export function sumInvoiceLinesExVat(
  lines: { qty: number | ""; unit_ex_vat: string }[],
): number {
  return lines.reduce((sum, line) => {
    if (typeof line.qty !== "number" || line.qty <= 0) {
      return sum;
    }
    const unit = parsePriceInput(line.unit_ex_vat);
    if (unit === null || unit <= 0) {
      return sum;
    }
    return sum + line.qty * unit;
  }, 0);
}

export function computeInvoicePreview(subtotalExVat: number): {
  vat: number;
  totalIncVat: number;
} {
  const vat = roundHalfUp(subtotalExVat * 0.15, 2);
  const totalIncVat = roundHalfUp(subtotalExVat + vat, 2);
  return { vat, totalIncVat };
}

export function formatFxGainLoss(value: string): string {
  const amount = Number(value);
  if (!Number.isFinite(amount) || amount === 0) {
    return "R 0.00";
  }
  const prefix = amount > 0 ? "Gain " : "Loss ";
  return `${prefix}R ${Math.abs(amount).toFixed(2)}`;
}

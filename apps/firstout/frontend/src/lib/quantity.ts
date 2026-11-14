/** Stock quantities use Numeric(14,4). Validate before sending; never truncate input. */
export const QUANTITY_STEP = 0.0001;
export const MAX_QUANTITY = 9_999_999_999.9999;
export type QuantityMode = "positive" | "nonnegative" | "delta";

function decimalPlaces(value: number): number {
  const [mantissa, exponent = "0"] = Math.abs(value).toString().split("e");
  const fraction = mantissa.split(".")[1]?.length ?? 0;
  return Math.max(0, fraction - Number(exponent));
}

export function quantityError(value: number | "", mode: QuantityMode = "positive"): string | null {
  if (value === "") return "Enter a quantity.";
  if (!Number.isFinite(value)) return "Enter a finite quantity.";
  if (Math.abs(value) > MAX_QUANTITY) return "Quantity must be less than 10 billion.";
  if (decimalPlaces(value) > 4) return "Use at most 4 decimal places.";
  if (mode === "delta" && value === 0) return "Enter a nonzero quantity adjustment.";
  if (mode === "positive" && value <= 0) return "Quantity must be greater than zero.";
  if (mode === "nonnegative" && value < 0) return "Quantity cannot be negative.";
  return null;
}

export function isQuantity(value: number | "", mode: QuantityMode = "positive"): value is number {
  return quantityError(value, mode) === null;
}

// Match the decimal point used by quantity inputs and existing stock tables.
const quantityFormatter = new Intl.NumberFormat("en-GB", {
  maximumFractionDigits: 4,
  useGrouping: false,
});

/** Display server quantities and small binary arithmetic noise without integer rounding. */
export function formatQuantity(value: number): string {
  return Number.isFinite(value) ? quantityFormatter.format(value) : "—";
}

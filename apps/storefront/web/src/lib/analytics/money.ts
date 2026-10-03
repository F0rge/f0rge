const MAX_MINOR = 1_000_000_000_00;

/** Integer ZAR cents. Major-unit rands are rounded once at this boundary. */
export function zarMinorUnits(value: unknown): number | null {
  const amount = typeof value === "number"
    ? value
    : typeof value === "string" && value.trim() !== ""
      ? Number(value)
      : Number.NaN;
  if (!Number.isFinite(amount) || amount < 0) return null;
  const minor = Math.round((amount + Number.EPSILON) * 100);
  if (!Number.isSafeInteger(minor) || minor > MAX_MINOR) return null;
  return minor;
}

/** Accepts an integer that is already ZAR minor units. */
export function asMinorUnits(value: unknown): number | null {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0 && value <= MAX_MINOR
    ? value
    : null;
}

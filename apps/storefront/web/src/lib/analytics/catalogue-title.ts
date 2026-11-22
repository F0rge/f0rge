/** A bounded label taken from the public catalogue. */
export function catalogueProductTitle(value: unknown): string | null {
  if (typeof value !== "string" || value.length > 255 || /[\p{Cc}\p{Cs}\p{Zl}\p{Zp}\p{Bidi_Control}]/u.test(value)) return null;
  return value.trim() || null;
}

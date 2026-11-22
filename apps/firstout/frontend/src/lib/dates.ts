/**
 * The business date. Firstout trades in South Africa, so "today" is the
 * browser's local calendar day, never the UTC day `toISOString()` gives
 * (which is yesterday between 00:00 and 02:00 SAST).
 */
export function localIsoDate(date: Date = new Date()): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

const DEFAULT_TZ = "Africa/Johannesburg";

export function formatNextRun(iso: string | null, timezone: string): string {
  if (!iso) {
    return "—";
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleString("en-ZA", {
    timeZone: timezone || DEFAULT_TZ,
    dateStyle: "medium",
    timeStyle: "short",
  });
}

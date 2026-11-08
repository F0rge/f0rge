/** Hosts identify a requested tenant; the API independently verifies membership. */
export const RESERVED_SLUGS = new Set([
  "www",
  "api",
  "app",
  "admin",
  "mail",
  "status",
  "support",
  "billing",
  "signup",
  "login",
  "static",
  "cdn",
  "trade",
]);
const SLUG = /^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$/;
export function frontendHost(
  host: string | null,
  allowLocal = false,
): string | null {
  if (!host || host !== host.trim() || /[\s,@/\\?#]/.test(host)) return null;
  const normalized = host.toLowerCase();
  if (allowLocal && /^(localhost|127\.0\.0\.1)(:[0-9]{1,5})?$/.test(normalized))
    return normalized;
  if (
    ["firstout.co.za", "www.firstout.co.za", "app.firstout.co.za"].includes(
      normalized,
    )
  )
    return normalized;
  const suffix = ".app.firstout.co.za";
  if (!normalized.endsWith(suffix)) return null;
  const slug = normalized.slice(0, -suffix.length);
  return SLUG.test(slug) && !RESERVED_SLUGS.has(slug) ? normalized : null;
}

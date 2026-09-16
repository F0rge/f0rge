/**
 * Placeholder product brand. The product is not "Vellano" (Vellano is company one).
 * Rename here only — every page reads from this object.
 */
export const tenantBaseDomain =
  process.env.NEXT_PUBLIC_TENANT_BASE_DOMAIN || "localhost";

export const site = {
  name: "Stockroom",
  domain: "stockroom.example",
  tagline: "Company software, built for humans.",
  description:
    "Back office for companies that buy, hold, and sell physical stock in South Africa. Each company gets its own hostname and Postgres database. An accepted quote holds stock; a delivery can be invoiced; the VAT201 draft is a read of that ledger. ZAR and 15% VAT are defaults.",
  supportEmail: "hello@stockroom.example",
  privacyVersion: "2026-09-draft",
  operatorName: "Stockroom (operator)",
} as const;

export function workspaceUrl(slug: string): string {
  return `${slug || "yourcompany"}.${tenantBaseDomain}`;
}

export function workspaceLoginUrl(slug: string): string {
  if (tenantBaseDomain === "localhost") {
    return `http://${slug}.localhost:3003/login`;
  }
  return `https://${slug}.${tenantBaseDomain}/login`;
}

export function loginHrefFromWorkspaceOrigin(origin: string): string {
  return origin.endsWith("/login") ? origin : `${origin.replace(/\/$/, "")}/login`;
}

export function slugFromHostInput(value: string): string {
  let host = value.trim().toLowerCase().replace(/^https?:\/\//, "");
  host = host.split("/")[0] ?? host;
  host = host.split(":")[0] ?? host;
  for (const suffix of [`.${tenantBaseDomain}`, `.${site.domain}`]) {
    if (host.endsWith(suffix)) {
      host = host.slice(0, -suffix.length);
    }
  }
  return host;
}

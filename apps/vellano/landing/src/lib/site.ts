/**
 * Placeholder product brand. The product is not "Vellano" (Vellano is customer #1).
 * Rename here only — every page reads from this object.
 */
export const site = {
  name: "Stockroom",
  domain: "stockroom.example",
  tagline: "Stock, till, and books — one back office for furniture retailers.",
  description:
    "Quotes to delivery to VAT201, with your own workspace on your own address and your data in your own database.",
  supportEmail: "hello@stockroom.example",
  privacyVersion: "2026-09-draft",
  operatorName: "Stockroom (operator)",
} as const;

export function workspaceUrl(slug: string): string {
  return `${slug || "yourcompany"}.${site.domain}`;
}

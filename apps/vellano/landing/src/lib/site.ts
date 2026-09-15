/**
 * Placeholder product brand. The product is not "Vellano" (Vellano is company one).
 * Rename here only — every page reads from this object.
 */
export const site = {
  name: "Stockroom",
  domain: "stockroom.example",
  tagline: "Stock, till, and books in one company workspace.",
  description:
    "Each company gets its own hostname and its own database. A quote that is accepted holds stock; a delivery can be invoiced; the VAT201 draft is a read of that ledger. ZAR and 15% VAT are defaults.",
  supportEmail: "hello@stockroom.example",
  privacyVersion: "2026-09-draft",
  operatorName: "Stockroom (operator)",
} as const;

export function workspaceUrl(slug: string): string {
  return `${slug || "yourcompany"}.${site.domain}`;
}

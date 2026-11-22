import type { CustomerCrm, PriceList, SaleLinePrice, SalePricePreview, Sku } from "@/lib/api";

import { permissionLabel } from "./permissions";
import { isCin7GeneratedPriceList } from "./price-lists";

/**
 * The browser's side of Sale line pricing (Firstout ADR 0001): it never prices a line, it
 * lines the server's preview up with what is on screen.
 *
 * The server returns one preview line per request line, in request order (free-text lines
 * included). A preview line whose SKU does not match the request line at that index is from
 * a stale request and is not shown.
 */
export function alignPreviewLines(
  skuIds: readonly (string | null)[],
  preview: SalePricePreview | undefined,
): (SaleLinePrice | undefined)[] {
  return skuIds.map((skuId, index) => {
    const line = preview?.lines[index];
    return line && (line.sku_id ?? null) === skuId ? line : undefined;
  });
}

/** Why the server will refuse this line's discount or price (ADR 0002), in plain words. */
export function blockedReason(blockedBy: string | null | undefined): string | null {
  if (!blockedBy) return null;
  if (blockedBy === "users.manage") {
    return `The discount is above the team's cap. Only staff who can "${permissionLabel("users.manage")}" can go higher.`;
  }
  if (blockedBy === "till.discount") {
    return `You can't give this discount: it needs "${permissionLabel("till.discount")}".`;
  }
  if (blockedBy === "sales.price_override") {
    return `You can't change this unit price: it needs "${permissionLabel("sales.price_override")}".`;
  }
  return `This line needs "${permissionLabel(blockedBy)}".`;
}

/** A saved line's discount. Null is a line stored before discounts were kept: its unit is already net. */
export function formatDiscount(discountPercent: string | null | undefined): string {
  const value = Number(discountPercent ?? 0);
  return value > 0 ? `${value}%` : "—";
}

const TIER_FIELD = {
  Stockist: "stockist_ex_vat",
  Wholesale: "wholesale_ex_vat",
  Decorator: "decorator_ex_vat",
  Retail: "retail_ex_vat",
} as const;

/**
 * Whether a finder offers the SKU: a gate, not a price. With a hand-made price list the
 * server decides once the SKU is on a line (its error shows on the cart). Otherwise the
 * server tries the customer's own tier, then Retail, and refuses the whole cart when
 * neither is set, so only those SKUs are offered. Cin7 lists are skipped as the server
 * skips them; no customer is Retail.
 */
export function mayBePriced(
  sku: Pick<Sku, "retail_ex_vat" | "wholesale_ex_vat" | "stockist_ex_vat" | "decorator_ex_vat">,
  customer: Pick<CustomerCrm, "price_list_id" | "price_classification"> | null | undefined,
  priceLists: readonly Pick<PriceList, "id" | "name">[],
): boolean {
  const list = customer?.price_list_id
    ? priceLists.find((entry) => entry.id === customer.price_list_id)
    : undefined;
  if (list && !isCin7GeneratedPriceList(list.name)) return true;
  const tier = TIER_FIELD[customer?.price_classification ?? "Retail"];
  return Number(sku.retail_ex_vat ?? 0) > 0 || Number(sku[tier] ?? 0) > 0;
}

/** A line the server will refuse to save: its discount or price needs a permission (ADR 0002). */
export function anyLineBlocked(preview: SalePricePreview | undefined): boolean {
  return preview?.lines.some((line) => line.blocked_by) ?? false;
}

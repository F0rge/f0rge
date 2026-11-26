/** Shapes header search answers into one flat, keyboard-navigable option list. */

import type { components } from "./generated/api-schema";

type Schema = components["schemas"];
type SearchResponse = Schema["SearchResponse"];
type SkuHit = Schema["SkuSearchHit"];

interface AdminHit {
  href: string;
  label: string;
  description?: string;
}

export type SearchOption =
  | { kind: "sku"; key: string; href: string; hit: SkuHit }
  | { kind: "link"; key: string; href: string; label: string; meta?: string };

export interface SearchGroup {
  label: string;
  options: { option: SearchOption; index: number }[];
}

/** Groups in display order (Administration destinations, only passed on Admin pages, then SKUs), each option carrying its index in the flat list. */
export function searchGroups(results: SearchResponse | undefined, admin: readonly AdminHit[]): { groups: SearchGroup[]; options: SearchOption[] } {
  const raw: { label: string; options: SearchOption[] }[] = [
    {
      label: "Administration",
      options: admin.map((hit) => ({ kind: "link", key: "admin:" + hit.href, href: hit.href, label: hit.label, meta: hit.description })),
    },
    {
      label: "SKUs",
      options: (results?.skus ?? []).map((hit) => ({ kind: "sku", key: "sku:" + hit.id, href: "/catalogue/" + hit.id, hit })),
    },
    {
      label: "Purchase orders",
      options: (results?.purchase_orders ?? []).map((order) => ({
        kind: "link",
        key: "po:" + order.id,
        href: "/purchase-orders/" + order.id,
        label: order.po_number + " · " + order.supplier_name,
        meta: order.status.replaceAll("_", " "),
      })),
    },
    {
      label: "Invoices",
      options: (results?.invoices ?? []).map((invoice) => ({
        kind: "link",
        key: "invoice:" + invoice.id,
        href: "/invoices/" + invoice.id,
        label: invoice.invoice_number + " · " + invoice.customer_name,
      })),
    },
  ];
  const options: SearchOption[] = [];
  const groups = raw
    .filter((group) => group.options.length > 0)
    .map((group) => ({
      label: group.label,
      options: group.options.map((option) => {
        options.push(option);
        return { option, index: options.length - 1 };
      }),
    }));
  return { groups, options };
}

/** Next highlighted index, wrapping at both ends; -1 when there is nothing to highlight. */
export function moveHighlight(current: number, delta: number, count: number): number {
  if (count <= 0) return -1;
  if (current < 0) return delta > 0 ? 0 : count - 1;
  return (current + delta + count) % count;
}

/** The SKU ids of the results, in order: the stepping context when a hit docks the panel. */
export function skuIds(options: readonly SearchOption[]): string[] {
  return options.flatMap((option) => (option.kind === "sku" ? [option.hit.id] : []));
}

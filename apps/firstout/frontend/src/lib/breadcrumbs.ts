import {
  ADMIN_NAV_ITEMS,
  BOOKS_NAV_ITEMS,
  CATALOGUE_NAV_ITEMS,
  SALES_NAV_ITEMS,
  STOCK_NAV_ITEMS,
  WAREHOUSE_NAV_ITEMS,
} from "./nav";

export type AppCrumb = { label: string; href?: string };
const groups = [
  { label: "Catalogue management", items: CATALOGUE_NAV_ITEMS },
  { label: "Stock", items: STOCK_NAV_ITEMS },
  { label: "Warehouse", items: WAREHOUSE_NAV_ITEMS },
  { label: "Sales", items: SALES_NAV_ITEMS },
  { label: "Books", items: BOOKS_NAV_ITEMS },
  { label: "Administration", items: ADMIN_NAV_ITEMS },
];
const detailLabels: Record<string, string> = {
  "/catalogue": "Product details",
  "/suppliers": "Supplier details",
  "/customers": "Customer details",
  "/purchase-orders": "Purchase order",
  "/picks": "Pick",
  "/invoices": "Invoice",
  "/bills": "Bill",
};

/** Groups are labels, not invented links. Only ancestors with real routes link. */
export function breadcrumbsForPath(pathname: string): AppCrumb[] {
  const path = pathname.replace(/\/+$/, "") || "/";
  if (path === "/" || path === "/till") return [];
  for (const group of groups) {
    const item = group.items.find(
      ({ href }) => path === href || path.startsWith(`${href}/`),
    );
    if (!item) continue;
    const label = item.href === "/catalogue" ? "Products" : item.label;
    if (path === item.href) return [{ label: group.label }, { label }];
    const tail = path.slice(item.href.length + 1);
    const current =
      tail === "new"
        ? "Create product"
        : tail === "read"
          ? "Read document"
          : (detailLabels[item.href] ?? "Details");
    return [
      { label: group.label },
      { label, href: item.href },
      { label: current },
    ];
  }
  return [];
}

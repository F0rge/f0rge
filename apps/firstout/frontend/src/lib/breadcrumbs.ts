import { NAV_GROUPS } from "./nav";
import { reportsView } from "./reports-sections";

export type AppCrumb = { label: string; href?: string };

const detailLabels: Record<string, string> = {
  "/catalogue": "Product details",
  "/suppliers": "Supplier details",
  "/customers": "Customer details",
  "/purchase-orders": "Purchase order",
  "/picks": "Pick",
  "/invoices": "Invoice",
  "/bills": "Bill",
  "/quotes": "Quote",
};
const newLabels: Record<string, string> = {
  "/quotes": "New quote",
  "/bills": "Create bill",
  "/invoices": "Create invoice",
};

/**
 * Workspace breadcrumbs: group / page [/ detail]. Groups are labels, not invented links; only ancestors
 * with real routes link. Top-level pages and Administration pages (which have their own) return [].
 */
export function breadcrumbsForPath(pathname: string, search: string | URLSearchParams = ""): AppCrumb[] {
  const path = pathname.replace(/\/+$/, "") || "/";
  if (path === "/reports") {
    const view = reportsView(new URLSearchParams(search).get("section"));
    return view.sectionLabel ? [{ label: "Reports" }, { label: view.sectionLabel }] : [];
  }
  for (const group of NAV_GROUPS) {
    if (group.link) continue;
    const item = group.pages.find(({ href }) => path === href) ??
      group.pages.find(({ href }) => path.startsWith(`${href}/`));
    if (!item) continue;
    if (path === item.href) return [{ label: group.label }, { label: item.label }];
    const tail = path.slice(item.href.length + 1);
    const current =
      tail === "new"
        ? (newLabels[item.href] ?? "Create product")
        : tail === "read"
          ? "Read document"
          : (detailLabels[item.href] ?? "Details");
    return [
      { label: group.label },
      { label: item.label, href: item.href },
      { label: current },
    ];
  }
  return [];
}

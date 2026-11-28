import type { PermissionHolder, PermissionKey } from "./permissions";
import { can } from "./permissions";

/**
 * Who a page is in the sidebar for. Presentation only: hiding a link changes nothing the API
 * allows, and every page stays reachable by URL, header search and in-page links.
 *
 * - `everyone`: shown to every staff member.
 * - `actions`: holding any of these keys means the person can work on this page.
 * - `lookup`: holding any of these keys means looking things up here is part of their job.
 *   On a page that also has `actions` the item carries a quiet "view" tag; on a read-only page
 *   (no `actions`) it is a plain item.
 *
 * Decided from permission keys only, never from the role name: custom roles are named bundles of keys,
 * and the owner preset holds every key.
 */
export interface NavRule {
  everyone?: true;
  actions?: readonly PermissionKey[];
  lookup?: readonly PermissionKey[];
}

export type NavAccess = "do" | "view";

export function navAccess(rule: NavRule, user: PermissionHolder): NavAccess | null {
  if (rule.everyone) return "do";
  if (rule.actions?.some((key) => can(user, key))) return "do";
  if (rule.lookup?.some((key) => can(user, key))) return rule.actions ? "view" : "do";
  return null;
}

export interface NavPage extends NavRule {
  href: string;
  label: string;
  /** The phone-only Warehouse console: hidden by CSS on wide screens. */
  mobileOnly?: true;
}

export type NavGroupId = "home" | "till" | "sell" | "products" | "buy" | "warehouse" | "stock" | "books" | "reports";

export interface NavGroup {
  id: NavGroupId;
  label: string;
  /** Top-level one-click link (Home, Till) rather than a menu. */
  link?: true;
  pages: readonly NavPage[];
}

export const REPORT_SECTION_HREF = {
  sales: "/reports?section=sales",
  stock: "/reports?section=stock",
  books: "/reports?section=books",
} as const;

// Lookup sets, named once so the reasoning reads in one place.
const SELLS_OR_HANDLES_STOCK = ["till.sell", "sales.quotes", "stock.receive", "stock.transfer"] as const;
const STOCK_LOOKUP = [...SELLS_OR_HANDLES_STOCK, "catalogue.mutate", "po.raise"] as const;
const BUYING_OR_BOOKS = ["books.mutate", "catalogue.mutate", "po.raise"] as const;

/** The workspace sidebar: groups and pages in order. Admin is one link to the Administration shell (see admin-navigation.ts). */
export const NAV_GROUPS: readonly NavGroup[] = [
  { id: "home", label: "Home", link: true, pages: [{ href: "/", label: "Home", everyone: true }] },
  { id: "till", label: "Till", link: true, pages: [{ href: "/till", label: "Till", actions: ["till.sell"] }] },
  {
    id: "sell",
    label: "Sell",
    pages: [
      { href: "/quotes", label: "Quotes", actions: ["sales.quotes"] },
      // Refunds are taken on an order; warehouse accepts quotes into orders and delivers them.
      { href: "/orders", label: "Orders", actions: ["sales.orders", "sales.refunds"], lookup: ["sales.quotes", "sales.deliveries"] },
      { href: "/laybys", label: "Laybys", actions: ["sales.laybys"] },
      { href: "/invoices", label: "Invoices", actions: ["books.mutate"], lookup: ["till.sell"] },
      { href: "/returns", label: "Returns", actions: ["sales.returns"] },
      { href: "/credit-notes", label: "Credit notes", actions: ["books.mutate"] },
      // Credit limits and holds: users.manage or po.raise.
      { href: "/customers", label: "Customers", actions: ["sales.customers", "po.raise", "users.manage"] },
    ],
  },
  {
    id: "products",
    label: "Products",
    pages: [
      { href: "/catalogue", label: "Catalogue", actions: ["catalogue.mutate"], lookup: SELLS_OR_HANDLES_STOCK },
      { href: "/price-lists", label: "Price lists", actions: ["catalogue.mutate"], lookup: ["till.sell"] },
    ],
  },
  {
    id: "buy",
    label: "Buy",
    pages: [
      { href: "/reorder", label: "Reorder", actions: ["catalogue.mutate"] },
      { href: "/purchase-orders", label: "Purchase orders", actions: ["catalogue.mutate", "po.raise"] },
      { href: "/proformas", label: "Proformas", actions: ["catalogue.mutate"] },
      { href: "/suppliers", label: "Suppliers", actions: ["catalogue.mutate"], lookup: ["books.mutate"] },
    ],
  },
  {
    id: "warehouse",
    label: "Warehouse",
    pages: [
      { href: "/receive", label: "Receive", actions: ["stock.receive"] },
      { href: "/wms", label: "Warehouse", mobileOnly: true, actions: ["stock.receive", "stock.transfer", "till.sell", "sales.deliveries"] },
      { href: "/transit", label: "Transit", actions: ["catalogue.mutate"], lookup: ["stock.receive"] },
      { href: "/transfers", label: "Transfers", actions: ["stock.transfer", "till.sell"] },
      { href: "/picks", label: "Picks", actions: ["stock.transfer", "till.sell", "sales.deliveries"] },
      { href: "/deliveries", label: "Deliveries", actions: ["sales.deliveries"] },
    ],
  },
  {
    id: "stock",
    label: "Stock",
    pages: [
      { href: "/stock", label: "Stock on hand", lookup: STOCK_LOOKUP },
      { href: "/stock-by-bin", label: "Stock by bin", lookup: STOCK_LOOKUP },
      { href: "/stocktakes", label: "Stocktakes", actions: ["stock.receive"] },
      { href: "/adjustments", label: "Adjustments", actions: ["stock.receive"] },
    ],
  },
  {
    id: "books",
    label: "Books",
    pages: [
      { href: "/bills", label: "Bills", actions: ["books.mutate"] },
      { href: "/payments", label: "Payments", actions: ["books.mutate"] },
      { href: "/bank-reconciliation", label: "Bank reconciliation", actions: ["books.mutate"] },
      { href: "/journals", label: "Journals", actions: ["books.mutate", "books.journals"] },
      { href: "/repeating-invoices", label: "Repeating invoices", actions: ["books.mutate"] },
      { href: "/ledger", label: "Chart of accounts", actions: ["books.mutate"] },
      { href: "/vat201", label: "VAT201", actions: ["books.mutate"] },
      { href: "/books-periods", label: "Books periods", actions: ["books.mutate"] },
    ],
  },
  {
    id: "reports",
    label: "Reports",
    pages: [
      { href: REPORT_SECTION_HREF.sales, label: "Sales", lookup: BUYING_OR_BOOKS },
      { href: REPORT_SECTION_HREF.stock, label: "Stock", lookup: ["stock.cost.view", ...BUYING_OR_BOOKS] },
      { href: REPORT_SECTION_HREF.books, label: "Books", lookup: ["books.mutate", "books.journals"] },
      // Gated like GET /reports/commission.
      { href: "/commission", label: "Commission", actions: ["books.mutate", "users.manage"] },
    ],
  },
];

export interface VisibleNavPage extends NavPage {
  access: NavAccess;
}
export interface VisibleNavGroup extends Omit<NavGroup, "pages"> {
  pages: readonly VisibleNavPage[];
}

/** The sidebar for this person: pages they work on or look up; a group with nothing to show disappears. */
export function navGroupsFor(user: PermissionHolder): VisibleNavGroup[] {
  return NAV_GROUPS.map((group) => ({
    ...group,
    pages: group.pages.flatMap((page) => {
      const access = navAccess(page, user);
      return access ? [{ ...page, access }] : [];
    }),
  })).filter((group) => group.pages.length > 0);
}

function splitHref(href: string): { path: string; section: string | null } {
  const [path, query = ""] = href.split("?");
  return { path, section: new URLSearchParams(query).get("section") };
}

function pathMatches(pathname: string, path: string): boolean {
  return pathname === path || (path !== "/" && pathname.startsWith(`${path}/`));
}

/** The sidebar item for this page is the current one. `section` is the `?section=` value, for Reports. */
export function isNavLinkActive(pathname: string, href: string, section: string | null = null): boolean {
  const target = splitHref(href);
  return pathMatches(pathname, target.path) && (target.section === null || target.section === section);
}

/** The group containing this page (expanded on load), ignoring the Reports section. */
export function navGroupForPath(pathname: string): NavGroup | undefined {
  return NAV_GROUPS.find((group) => group.pages.some((page) => pathMatches(pathname, splitHref(page.href).path)));
}

/** Human label for a workspace page path — maps `/invoices/abc` → "Invoices", not the raw path. */
export function labelForNavPath(path: string): string {
  for (const group of NAV_GROUPS) {
    for (const page of group.pages) {
      if (pathMatches(path, page.href)) return page.label;
    }
  }
  return path;
}

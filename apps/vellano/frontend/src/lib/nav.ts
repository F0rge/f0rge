export const BOOKS_NAV_ITEMS = [
  { href: "/ledger", label: "Chart of accounts" },
  { href: "/journals", label: "Journals" },
  { href: "/contacts", label: "Contacts" },
  { href: "/invoices", label: "Invoices" },
  { href: "/repeating-invoices", label: "Repeating invoices" },
  { href: "/credit-notes", label: "Credit notes" },
  { href: "/bills", label: "Bills" },
  { href: "/payments", label: "Payments" },
  { href: "/bank-reconciliation", label: "Bank reconciliation" },
  { href: "/reports", label: "Reports" },
  { href: "/vat201", label: "VAT201" },
] as const;

export type BooksNavItem = (typeof BOOKS_NAV_ITEMS)[number];

export const PRIMARY_NAV_ITEMS = [
  { href: "/", label: "Home" },
  { href: "/locations", label: "Locations" },
  { href: "/suppliers", label: "Suppliers" },
  { href: "/proformas", label: "Proformas" },
  { href: "/catalogue", label: "Catalogue" },
] as const;

export const STOCK_NAV_ITEMS = [
  { href: "/stock", label: "Stock" },
  { href: "/stocktakes", label: "Stocktakes" },
  { href: "/adjustments", label: "Adjustments" },
  { href: "/import", label: "Import" },
  { href: "/reorder", label: "Reorder" },
] as const;

export const OPERATIONS_NAV_ITEMS = [
  { href: "/purchase-orders", label: "Purchase orders" },
  { href: "/transit", label: "Transit" },
  { href: "/receive", label: "Receive" },
  { href: "/wms", label: "WMS" },
  { href: "/transfers", label: "Transfers" },
  { href: "/picks", label: "Picks" },
  { href: "/deliveries", label: "Deliveries" },
  { href: "/till", label: "Till" },
  { href: "/laybys", label: "Laybys" },
] as const;

export const SALES_NAV_ITEMS = [
  { href: "/returns", label: "Returns" },
  { href: "/customers", label: "Customers" },
] as const;

export const NIA_NAV_ITEMS = [{ href: "/canvas", label: "Canvas" }] as const;

export const ACCOUNT_NAV_ITEMS = [
  { href: "/users", label: "Users", permission: "users.manage" as const },
  { href: "/roles", label: "Roles", permission: "users.manage" as const },
  { href: "/profile", label: "Profile" },
  { href: "/settings", label: "Settings" },
] as const;

const BOOKS_HREFS = new Set<string>(BOOKS_NAV_ITEMS.map((item) => item.href));
const STOCK_HREFS = new Set<string>(STOCK_NAV_ITEMS.map((item) => item.href));

export function isBooksPath(pathname: string): boolean {
  return (
    BOOKS_HREFS.has(pathname) ||
    pathname.startsWith("/journals/") ||
    pathname.startsWith("/invoices/") ||
    pathname.startsWith("/repeating-invoices/") ||
    pathname.startsWith("/credit-notes/") ||
    pathname.startsWith("/bills/")
  );
}

export function isStockPath(pathname: string): boolean {
  return STOCK_HREFS.has(pathname);
}

const ALL_NAV_PATH_LABELS: ReadonlyMap<string, string> = new Map(
  [
    ...PRIMARY_NAV_ITEMS,
    ...STOCK_NAV_ITEMS,
    ...OPERATIONS_NAV_ITEMS,
    ...SALES_NAV_ITEMS,
    ...BOOKS_NAV_ITEMS,
    ...NIA_NAV_ITEMS,
  ].map((item) => [item.href, item.label]),
);

/** Human label for Nia navigation cards — maps `/invoices` → "Invoices", not raw path. */
export function labelForNavPath(path: string): string {
  const exact = ALL_NAV_PATH_LABELS.get(path);
  if (exact) {
    return exact;
  }
  for (const [href, label] of ALL_NAV_PATH_LABELS) {
    if (href !== "/" && path.startsWith(`${href}/`)) {
      return label;
    }
  }
  return path;
}

export function isNavLinkActive(pathname: string, href: string): boolean {
  if (pathname === href) {
    return true;
  }
  if (href === "/journals" && pathname.startsWith("/journals/")) {
    return true;
  }
  if (href === "/invoices" && pathname.startsWith("/invoices/")) {
    return true;
  }
  if (href === "/repeating-invoices" && pathname.startsWith("/repeating-invoices/")) {
    return true;
  }
  if (href === "/credit-notes" && pathname.startsWith("/credit-notes/")) {
    return true;
  }
  if (href === "/bills" && pathname.startsWith("/bills/")) {
    return true;
  }
  if (href === "/purchase-orders" && pathname.startsWith("/purchase-orders/")) {
    return true;
  }
  if (href === "/catalogue" && pathname.startsWith("/catalogue/")) {
    return true;
  }
  if (href === "/customers" && pathname.startsWith("/customers/")) {
    return true;
  }
  if (href === "/picks" && pathname.startsWith("/picks/")) {
    return true;
  }
  return false;
}

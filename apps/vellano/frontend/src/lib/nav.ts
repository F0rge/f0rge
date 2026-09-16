export const BOOKS_NAV_ITEMS = [
  { href: "/ledger", label: "Chart of accounts" },
  { href: "/journals", label: "Journals" },
  { href: "/invoices", label: "Invoices" },
  { href: "/repeating-invoices", label: "Repeating invoices" },
  { href: "/credit-notes", label: "Credit notes" },
  { href: "/bills", label: "Bills" },
  { href: "/payments", label: "Payments" },
  { href: "/bank-reconciliation", label: "Bank reconciliation" },
  { href: "/reports", label: "Reports" },
  { href: "/vat201", label: "VAT201" },
  { href: "/books-periods", label: "Books periods" },
] as const;

export type BooksNavItem = (typeof BOOKS_NAV_ITEMS)[number];

/** Top-level 1-click items (not in a menu). */
export const HOME_NAV_ITEM = { href: "/", label: "Home" } as const;
export const TILL_NAV_ITEM = { href: "/till", label: "Till" } as const;

export const CATALOGUE_NAV_ITEMS = [
  { href: "/catalogue", label: "Catalogue" },
  { href: "/suppliers", label: "Suppliers" },
  { href: "/price-lists", label: "Price lists" },
  { href: "/proformas", label: "Proformas" },
  { href: "/locations", label: "Locations" },
] as const;

/** Stock workflows — no standalone /stock inventory list. */
export const STOCK_NAV_ITEMS = [
  { href: "/stocktakes", label: "Stocktakes" },
  { href: "/adjustments", label: "Adjustments" },
  { href: "/import", label: "Import" },
  { href: "/reorder", label: "Reorder" },
] as const;

export const WAREHOUSE_NAV_ITEMS = [
  { href: "/purchase-orders", label: "Purchase orders" },
  { href: "/transit", label: "Transit" },
  { href: "/receive", label: "Receive" },
  { href: "/wms", label: "Warehouse", mobileOnly: true },
  { href: "/transfers", label: "Transfers" },
  { href: "/picks", label: "Picks" },
] as const;

export const SALES_NAV_ITEMS = [
  { href: "/quotes", label: "Quotes" },
  { href: "/lookbooks", label: "Lookbooks" },
  { href: "/orders", label: "Orders" },
  { href: "/laybys", label: "Laybys" },
  { href: "/customers", label: "Customers" },
  { href: "/returns", label: "Returns" },
  { href: "/deliveries", label: "Deliveries" },
] as const;

export const NIA_NAV_ITEMS = [{ href: "/canvas", label: "Canvas" }] as const;

export const ADMIN_NAV_ITEMS = [
  { href: "/users", label: "Users", permission: "users.manage" as const },
  { href: "/roles", label: "Roles", permission: "users.manage" as const },
  { href: "/audit", label: "Audit" },
  { href: "/profile", label: "Profile" },
  { href: "/settings", label: "Settings" },
] as const;

/** @deprecated Prefer ADMIN_NAV_ITEMS — kept for any stray imports during transition. */
export const ACCOUNT_NAV_ITEMS = ADMIN_NAV_ITEMS;

/** Flat primary list before regroup — Home only; catalogue moved into CATALOGUE_NAV_ITEMS. */
export const PRIMARY_NAV_ITEMS = [HOME_NAV_ITEM] as const;

/** Flat ops list before regroup — Till only. */
export const OPERATIONS_NAV_ITEMS = [TILL_NAV_ITEM] as const;

const BOOKS_HREFS = new Set<string>(BOOKS_NAV_ITEMS.map((item) => item.href));
const STOCK_HREFS = new Set<string>(STOCK_NAV_ITEMS.map((item) => item.href));
const CATALOGUE_HREFS = new Set<string>(CATALOGUE_NAV_ITEMS.map((item) => item.href));
const WAREHOUSE_HREFS = new Set<string>(WAREHOUSE_NAV_ITEMS.map((item) => item.href));
const SALES_HREFS = new Set<string>(SALES_NAV_ITEMS.map((item) => item.href));
const ADMIN_HREFS = new Set<string>(ADMIN_NAV_ITEMS.map((item) => item.href));

export function isBooksPath(pathname: string): boolean {
  return (
    BOOKS_HREFS.has(pathname) ||
    pathname.startsWith("/journals/") ||
    pathname.startsWith("/invoices/") ||
    pathname.startsWith("/repeating-invoices/") ||
    pathname.startsWith("/credit-notes/") ||
    pathname.startsWith("/bills/") ||
    pathname.startsWith("/books-periods")
  );
}

export function isStockPath(pathname: string): boolean {
  return STOCK_HREFS.has(pathname);
}

export function isCatalogueMenuPath(pathname: string): boolean {
  if (CATALOGUE_HREFS.has(pathname)) {
    return true;
  }
  return pathname.startsWith("/catalogue/");
}

export function isWarehousePath(pathname: string): boolean {
  return (
    WAREHOUSE_HREFS.has(pathname) || pathname.startsWith("/purchase-orders/") || pathname.startsWith("/picks/")
  );
}

export function isSalesPath(pathname: string): boolean {
  return (
    SALES_HREFS.has(pathname) ||
    pathname.startsWith("/customers/") ||
    pathname.startsWith("/quotes/") ||
    pathname.startsWith("/lookbooks/") ||
    pathname.startsWith("/orders/")
  );
}

export function isAdminPath(pathname: string): boolean {
  return ADMIN_HREFS.has(pathname);
}

const ALL_NAV_PATH_LABELS: ReadonlyMap<string, string> = new Map(
  [
    HOME_NAV_ITEM,
    TILL_NAV_ITEM,
    ...CATALOGUE_NAV_ITEMS,
    ...STOCK_NAV_ITEMS,
    ...WAREHOUSE_NAV_ITEMS,
    ...SALES_NAV_ITEMS,
    ...BOOKS_NAV_ITEMS,
    ...NIA_NAV_ITEMS,
    ...ADMIN_NAV_ITEMS,
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
  if (href === "/quotes" && pathname.startsWith("/quotes/")) {
    return true;
  }
  if (href === "/orders" && pathname.startsWith("/orders/")) {
    return true;
  }
  if (href === "/picks" && pathname.startsWith("/picks/")) {
    return true;
  }
  return false;
}

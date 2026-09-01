export const BOOKS_NAV_ITEMS = [
  { href: "/ledger", label: "Chart of accounts" },
  { href: "/contacts", label: "Contacts" },
  { href: "/invoices", label: "Invoices" },
  { href: "/credit-notes", label: "Credit notes" },
  { href: "/bills", label: "Bills" },
  { href: "/payments", label: "Payments" },
  { href: "/bank-reconciliation", label: "Bank reconciliation" },
  { href: "/reports", label: "Reports" },
  { href: "/vat201", label: "VAT201 draft" },
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
  { href: "/transfers", label: "Transfers" },
  { href: "/deliveries", label: "Deliveries" },
  { href: "/till", label: "Till" },
] as const;

export const SALES_NAV_ITEMS = [
  { href: "/returns", label: "Returns" },
  { href: "/laybys", label: "Laybys" },
  { href: "/customers", label: "Customers" },
] as const;

export const ACCOUNT_NAV_ITEMS = [
  { href: "/users", label: "Users", ownerOnly: true as const },
  { href: "/profile", label: "Profile" },
  { href: "/settings", label: "Settings" },
] as const;

const BOOKS_HREFS = new Set<string>(BOOKS_NAV_ITEMS.map((item) => item.href));
const STOCK_HREFS = new Set<string>(STOCK_NAV_ITEMS.map((item) => item.href));

export function isBooksPath(pathname: string): boolean {
  return (
    BOOKS_HREFS.has(pathname) ||
    pathname.startsWith("/invoices/") ||
    pathname.startsWith("/credit-notes/") ||
    pathname.startsWith("/bills/")
  );
}

export function isStockPath(pathname: string): boolean {
  return STOCK_HREFS.has(pathname);
}

export function isNavLinkActive(pathname: string, href: string): boolean {
  if (pathname === href) {
    return true;
  }
  if (href === "/invoices" && pathname.startsWith("/invoices/")) {
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
  return false;
}

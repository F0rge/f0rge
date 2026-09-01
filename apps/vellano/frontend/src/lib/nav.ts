export const BOOKS_NAV_ITEMS = [
  { href: "/ledger", label: "Chart of accounts" },
  { href: "/contacts", label: "Contacts" },
  { href: "/invoices", label: "Invoices" },
  { href: "/bills", label: "Bills" },
  { href: "/payments", label: "Payments" },
  { href: "/bank-reconciliation", label: "Bank reconciliation" },
  { href: "/reports", label: "Reports" },
  { href: "/vat201", label: "VAT201 draft" },
] as const;

export type BooksNavItem = (typeof BOOKS_NAV_ITEMS)[number];

export const SIDE_NAV_ITEMS = [
  { href: "/", label: "Home" },
  { href: "/locations", label: "Locations" },
  { href: "/suppliers", label: "Suppliers" },
  { href: "/proformas", label: "Proformas" },
  { href: "/catalogue", label: "Catalogue" },
  { href: "/stock", label: "Stock" },
  { href: "/purchase-orders", label: "Purchase orders" },
  { href: "/transit", label: "Transit" },
  { href: "/receive", label: "Receive" },
  { href: "/transfers", label: "Transfers" },
  { href: "/till", label: "Till" },
  { href: "/users", label: "Users", ownerOnly: true },
  { href: "/profile", label: "Profile" },
  { href: "/settings", label: "Settings" },
] as const;

export type SideNavItem = (typeof SIDE_NAV_ITEMS)[number];

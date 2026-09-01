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
  { href: "/ledger", label: "Ledger" },
  { href: "/till", label: "Till" },
  { href: "/users", label: "Users", ownerOnly: true },
  { href: "/profile", label: "Profile" },
  { href: "/settings", label: "Settings" },
] as const;

export type SideNavItem = (typeof SIDE_NAV_ITEMS)[number];

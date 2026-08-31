export const SIDE_NAV_ITEMS = [
  { href: "/", label: "Home" },
  { href: "/locations", label: "Locations" },
  { href: "/stock", label: "Stock" },
  { href: "/purchase-orders", label: "Purchase orders" },
  { href: "/ledger", label: "Ledger" },
  { href: "/till", label: "Till" },
  { href: "/users", label: "Users", ownerOnly: true },
  { href: "/profile", label: "Profile" },
  { href: "/settings", label: "Settings" },
] as const;

export type SideNavItem = (typeof SIDE_NAV_ITEMS)[number];

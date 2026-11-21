// The four shop categories: Medusa product category handles, created by the commerce bootstrap (#1002).
export const SHOP_CATEGORIES = [
  { handle: "sofas-armchairs", name: "Sofas & Armchairs", blurb: "Sofas and armchairs for the living room.", href: "/shop/sofas-armchairs" },
  { handle: "dining-room", name: "Dining Room", blurb: "Dining tables and chairs.", href: "/shop/dining-room" },
  { handle: "bedroom", name: "Bedroom", blurb: "Pieces for the bedroom.", href: "/shop/bedroom" },
  { handle: "coffee-console-tables", name: "Coffee & Console Tables", blurb: "Coffee and console tables.", href: "/shop/coffee-console-tables" },
] as const;

export type ShopCategory = (typeof SHOP_CATEGORIES)[number];

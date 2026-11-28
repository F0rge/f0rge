// The four shop categories: Medusa product category handles, created by the commerce bootstrap (#1002).
export const SHOP_CATEGORIES = [
  {
    handle: "sofas-armchairs",
    name: "Sofas & Armchairs",
    blurb: "Compare straight sofas, corner sofas and armchairs for your living room.",
    href: "/shop/sofas-armchairs",
    pageCopy: {
      heading: "Find a sofa or armchair",
      title: "Sofa & Armchair Shop in Bedfordview",
      description: "Find a sofa or armchair at DasKasas. Compare sizes and finishes online or visit the showroom at Bedford Square, Bedfordview.",
    },
  },
  { handle: "dining-room", name: "Dining Room", blurb: "Dining tables and chairs.", href: "/shop/dining-room" },
  {
    handle: "bedroom",
    name: "Bedroom",
    blurb: "Beds, headboards and bedside tables.",
    href: "/shop/bedroom",
    pageCopy: {
      heading: "Bedroom",
      title: "Bedroom Furniture in Bedfordview",
      description: "Shop beds, headboards and bedside tables at DasKasas. Compare dimensions online or visit the showroom at Bedford Square, Bedfordview.",
    },
  },
  { handle: "coffee-console-tables", name: "Coffee & Console Tables", blurb: "Coffee and console tables.", href: "/shop/coffee-console-tables" },
] as const;

export type ShopCategory = (typeof SHOP_CATEGORIES)[number];

export const AVANZI_SOFA_PATH = "/product/7d36b7b6-9871-44c5-b330-b808221f8005";

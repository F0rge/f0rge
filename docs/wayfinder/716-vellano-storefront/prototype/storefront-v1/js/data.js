/**
 * THROWAWAY PROTOTYPE — mock catalogue for Vellano storefront UI (#720).
 * Question: what should greenfield furniture Storefront look/feel like?
 * Three variants via ?v=editorial|scandi|industrial — not production architecture.
 */
window.VellanoProto = window.VellanoProto || {};

VellanoProto.BRAND = {
  name: "Vellano",
  tagline: "Curated furniture for South African homes",
  currency: "ZAR",
  vatNote: "Prices include 15% VAT",
};

VellanoProto.SHIPPING = [
  {
    id: "showroom",
    label: "Collect from showroom",
    detail: "Johannesburg Design District — free",
    price: 0,
    eta: "Ready in 2–3 business days",
  },
  {
    id: "gauteng",
    label: "Gauteng delivery",
    detail: "White-glove to door",
    price: 450,
    eta: "3–7 business days",
  },
  {
    id: "national",
    label: "National domestic",
    detail: "Major centres · kerbside",
    price: 950,
    eta: "7–14 business days",
  },
];

VellanoProto.PRODUCTS = [
  {
    id: "kalahari-sofa",
    name: "Kalahari Lounge Sofa",
    collection: "Living",
    priceFrom: 24900,
    blurb: "Deep seat, kiln-dried frame, removable covers.",
    hue: "#8b7355",
    fabrics: ["Sand Linen", "Charcoal Wool", "Olive Velvet"],
    sizes: ["2.5-seater", "3-seater", "Corner"],
    defaultFabric: "Sand Linen",
    defaultSize: "3-seater",
    skuMods: { "2.5-seater": 0, "3-seater": 3200, Corner: 8900 },
  },
  {
    id: "table-mountain",
    name: "Table Mountain Dining Table",
    collection: "Dining",
    priceFrom: 18900,
    blurb: "Solid ash top, sculpted legs, seats 6–10.",
    hue: "#6b5344",
    fabrics: ["Natural Ash", "Smoked Oak", "Ebony Stain"],
    sizes: ["180 cm", "210 cm", "240 cm"],
    defaultFabric: "Natural Ash",
    defaultSize: "210 cm",
    skuMods: { "180 cm": 0, "210 cm": 2400, "240 cm": 4800 },
  },
  {
    id: "karoo-chair",
    name: "Karoo Accent Chair",
    collection: "Living",
    priceFrom: 7900,
    blurb: "Wide arms, bounce-back foam, showroom favourite.",
    hue: "#a67c52",
    fabrics: ["Cream Bouclé", "Terracotta", "Ink"],
    sizes: ["Standard"],
    defaultFabric: "Cream Bouclé",
    defaultSize: "Standard",
    skuMods: { Standard: 0 },
  },
  {
    id: "cape-sideboard",
    name: "Cape Oak Sideboard",
    collection: "Dining",
    priceFrom: 16400,
    blurb: "Cable-managed media bay, soft-close drawers.",
    hue: "#7a5c45",
    fabrics: ["Light Oak", "Walnut"],
    sizes: ["160 cm", "200 cm"],
    defaultFabric: "Light Oak",
    defaultSize: "160 cm",
    skuMods: { "160 cm": 0, "200 cm": 2800 },
  },
  {
    id: "drakensberg-bed",
    name: "Drakensberg Bed Frame",
    collection: "Bedroom",
    priceFrom: 14500,
    blurb: "Upholstered headboard, slatted base, no box spring.",
    hue: "#5c4a3a",
    fabrics: ["Stone Linen", "Midnight", "Rust"],
    sizes: ["Queen", "King"],
    defaultFabric: "Stone Linen",
    defaultSize: "Queen",
    skuMods: { Queen: 0, King: 2100 },
  },
  {
    id: "fynbos-coffee",
    name: "Fynbos Coffee Table",
    collection: "Living",
    priceFrom: 6200,
    blurb: "Low oval top, nested stool option.",
    hue: "#9a8570",
    fabrics: ["Travertine", "Blackened Steel"],
    sizes: ["Ø90 cm", "Ø110 cm"],
    defaultFabric: "Travertine",
    defaultSize: "Ø90 cm",
    skuMods: { "Ø90 cm": 0, "Ø110 cm": 900 },
  },
  {
    id: "waterfront-lamp",
    name: "Waterfront Floor Lamp",
    collection: "Lighting",
    priceFrom: 3800,
    blurb: "Brushed brass stem, linen drum shade.",
    hue: "#c4a574",
    fabrics: ["Brass / Ivory", "Black / Smoke"],
    sizes: ["160 cm"],
    defaultFabric: "Brass / Ivory",
    defaultSize: "160 cm",
    skuMods: { "160 cm": 0 },
  },
  {
    id: "swartland-shelf",
    name: "Swartland Bookshelf",
    collection: "Storage",
    priceFrom: 11200,
    blurb: "Open bays + closed cupboard, adjustable shelves.",
    hue: "#4a3f35",
    fabrics: ["White Wash", "Natural Pine"],
    sizes: ["High", "Low wide"],
    defaultFabric: "Natural Pine",
    defaultSize: "High",
    skuMods: { High: 0, "Low wide": 800 },
  },
];

VellanoProto.fmt = function (centsOrRands) {
  const n = Math.round(centsOrRands);
  return "R\u00a0" + n.toLocaleString("en-ZA");
};

VellanoProto.skuPrice = function (product, size) {
  const mod = (product.skuMods && product.skuMods[size]) || 0;
  return product.priceFrom + mod;
};

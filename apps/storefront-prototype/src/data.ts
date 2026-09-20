export type Product = {
  id: string;
  name: string;
  type: string;
  category: string;
  price: number;
  image: string;
  scene: string;
  material: string;
  description: string;
  dimensions: [number, number, number];
  stock: number;
  finishes: { name: string; color: string; extra: number }[];
  badge?: string;
  position?: string;
};
export const img = (name: string) => `/images/${name}.jpg`;
export const products: Product[] = [
  {
    id: "terra",
    name: "Terra",
    type: "Three-seater sofa",
    category: "Sofas",
    price: 28900,
    image: "bi-sofa-06",
    scene: "bi-sofa-06",
    material: "Textured linen · Solid oak",
    description:
      "An invitation to settle in. Generous proportions, beautifully textured linen and a grounded silhouette bring a quiet warmth to the everyday.",
    dimensions: [230, 98, 78],
    stock: 4,
    finishes: [
      { name: "Natural linen", color: "#b6b0a3", extra: 0 },
      { name: "Olive linen", color: "#757c60", extra: 1200 },
      { name: "Charcoal linen", color: "#555652", extra: 1200 },
    ],
    badge: "A Vellano favourite",
    position: "50% 62%",
  },
  {
    id: "rue",
    name: "Rue",
    type: "Occasional chair",
    category: "Chairs",
    price: 7900,
    image: "club-chair",
    scene: "walnut-lounge",
    material: "Soft woven cotton · Turned wood",
    description:
      "A softly sculpted seat for a slow morning or a well-loved book. The Rue brings an easy elegance to your favourite corner.",
    dimensions: [76, 82, 84],
    stock: 3,
    finishes: [
      { name: "Chalk", color: "#e3ddcb", extra: 0 },
      { name: "Sand", color: "#c8b698", extra: 600 },
    ],
    position: "50% 65%",
  },
  {
    id: "vale",
    name: "Vale",
    type: "Bedside table",
    category: "Tables",
    price: 4950,
    image: "marble-coffee",
    scene: "sand-modular",
    material: "Natural solid oak",
    description:
      "Honest grain, softened edges and just enough room for your evening essentials. A small piece with a beautifully useful purpose.",
    dimensions: [48, 38, 52],
    stock: 7,
    finishes: [
      { name: "Natural oak", color: "#bda17d", extra: 0 },
      { name: "Smoked oak", color: "#6d5745", extra: 450 },
    ],
    badge: "New perspective",
  },
  {
    id: "forma",
    name: "Forma",
    type: "Chaise sofa",
    category: "Sofas",
    price: 36900,
    image: "modular-cloud",
    scene: "modular-cloud",
    material: "Linen blend · Hardwood frame",
    description:
      "Room for everyone, space for yourself. Deep, relaxed seating and a generous chaise make the Forma the natural heart of the home.",
    dimensions: [290, 170, 80],
    stock: 2,
    finishes: [
      { name: "Oat linen", color: "#cbc6b5", extra: 0 },
      { name: "Warm grey", color: "#9d9c94", extra: 1500 },
    ],
    position: "60% 65%",
  },
  {
    id: "oslo",
    name: "Oslo",
    type: "Velvet sofa",
    category: "Sofas",
    price: 24900,
    image: "london-3s",
    scene: "outdoor-teak",
    material: "Cotton velvet · Walnut legs",
    description:
      "A classic line, a deeper colour. Plush forest velvet and the warmth of walnut create a piece that feels collected, never ordinary.",
    dimensions: [210, 90, 82],
    stock: 5,
    finishes: [
      { name: "Forest velvet", color: "#34544d", extra: 0 },
      { name: "Cocoa velvet", color: "#786153", extra: 900 },
    ],
  },
  {
    id: "gather",
    name: "Gather",
    type: "Six-seat dining table",
    category: "Tables",
    price: 18900,
    image: "bi-dining-01",
    scene: "bi-dining-01",
    material: "Stone-look top · Solid timber",
    description:
      "For long lunches and conversations that carry on. Balanced proportions and a tactile surface make every gathering feel a little more considered.",
    dimensions: [200, 95, 76],
    stock: 3,
    finishes: [
      { name: "Warm stone", color: "#d6cdbb", extra: 0 },
      { name: "Walnut", color: "#765540", extra: 1000 },
    ],
  },
  {
    id: "lume",
    name: "Lume",
    type: "Pendant light",
    category: "Lighting",
    price: 2950,
    image: "bi-lamp-01",
    scene: "bi-lamp-01",
    material: "Powder-coated aluminium",
    description:
      "A simple form, a softer atmosphere. Thoughtfully diffused light for the places where life unfolds.",
    dimensions: [36, 36, 42],
    stock: 0,
    finishes: [
      { name: "Soft grey", color: "#9c9d98", extra: 0 },
      { name: "Warm white", color: "#e3dfd4", extra: 0 },
    ],
    badge: "Returning soon",
  },
  {
    id: "haven",
    name: "Haven",
    type: "Lounge collection",
    category: "Chairs",
    price: 11900,
    image: "walnut-lounge",
    scene: "walnut-lounge",
    material: "Natural weave · Oak",
    description:
      "Lightness, texture, a sense of home. An easy lounge piece that sits comfortably in spaces both classic and contemporary.",
    dimensions: [82, 88, 79],
    stock: 4,
    finishes: [
      { name: "Natural weave", color: "#d4ccba", extra: 0 },
      { name: "Tobacco", color: "#a77a55", extra: 800 },
    ],
  },
];
export const money = (value: number) =>
  "R " +
  new Intl.NumberFormat("en-ZA", { maximumFractionDigits: 0 })
    .format(value)
    .replace(/,/g, " ");
export const variantNames = [
  "The Editorial",
  "The Atelier",
  "The Gallery",
  "The Collector",
];
export const heroSlides = [
  {
    image: "bi-sofa-06",
    title: ["A considered home.", "A beautiful life."],
    label: "THE NEW PERSPECTIVES COLLECTION",
    product: "terra",
    caption: "The Terra sofa · Natural linen",
  },
  {
    image: "modular-cloud",
    title: ["Room to gather.", "Space to unwind."],
    label: "THE LIVING COLLECTION",
    product: "forma",
    caption: "The Forma chaise · Oat linen",
  },
  {
    image: "bi-dining-01",
    title: ["Come together.", "Stay a little longer."],
    label: "AT HOME, AROUND THE TABLE",
    product: "gather",
    caption: "The Gather table · Warm stone",
  },
];

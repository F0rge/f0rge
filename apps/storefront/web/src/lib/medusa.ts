import "server-only";
import { formatCustomerPrice, isZarCurrency } from "./order-money";
import { offerLive } from "./made-to-order";
import { selectedImages } from "./product-variants";
import { sellCount, sellRules, type SellRules } from "./sell-rules";

type MedusaRegion = { id: string; currency_code: string };
export type MedusaImage = { id: string; url: string };
export type MedusaOption = { id: string; title: string; values?: { id: string; value: string }[] };
export type MadeToOrderOffer = {
  id: string;
  capacity: number;
  min_lead_time_days: number;
  max_lead_time_days: number;
  expires_at: string;
  remaining_capacity: number;
  observed_at?: string | null;
};
export type FulfillmentPromise = {
  kind: "stocked" | "made_to_order";
  offer_id?: string;
  min_lead_time_days?: number;
  max_lead_time_days?: number;
  estimated_from: string;
  estimated_by: string;
  expires_at?: string;
};
export type DimensionsCm = {
  width: number | null;
  depth: number | null;
  height: number | null;
  diameter: number | null;
};
export type MedusaVariant = {
  id: string;
  sku: string | null;
  title?: string;
  thumbnail?: string | null;
  images?: MedusaImage[] | null;
  options?: { id: string; value: string; option_id?: string | null; option?: { id: string; title: string } | null }[];
  metadata?: {
    suitable_image_urls?: string[] | string;
    dimensions_cm?: DimensionsCm | null;
    lead_time_days?: number | string;
    care_instructions?: string;
    made_to_order_offer?: MadeToOrderOffer | null;
    storefront_made_to_order_offer?: MadeToOrderOffer | null;
    swatch_hex?: string | null;
    /** Sold in multiples of this; absent means 1. */
    sell_multiple?: number;
    /** Least quantity per order; absent means 1. */
    min_quantity?: number;
  } | null;
  material?: string | null;
  length?: number | null;
  width?: number | null;
  height?: number | null;
  inventory_quantity?: number;
  // Medusa BaseCalculatedPriceSet; calculated_price.price_list_type is "sale" for a sale price list.
  calculated_price?: {
    calculated_amount: number;
    original_amount?: number | null;
    currency_code: string;
    calculated_price?: { price_list_type?: string | null } | null;
  };
};

export type StoreProduct = {
  id: string;
  handle: string;
  title: string;
  description: string | null;
  thumbnail?: string | null;
  images?: MedusaImage[];
  options?: MedusaOption[];
  metadata?: {
    care_instructions?: string;
    dimension_unit?: "cm" | "mm";
    seo_title?: string;
    seo_description?: string;
  } | null;
  material?: string | null;
  length?: number | null;
  width?: number | null;
  height?: number | null;
  variants: MedusaVariant[];
  categories?: { id: string; name: string; handle: string }[];
  tags?: { value: string }[];
  status?: string;
};

const baseUrl = process.env.MEDUSA_BACKEND_URL || "http://localhost:9000";
const publishableKey = process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY;
const productFields = "id,handle,title,description,thumbnail,material,length,width,height,metadata,*images,*options,*options.values,*categories,*tags,*variants,*variants.images,*variants.options,+variants.inventory_quantity,*variants.calculated_price,+variants.material,+variants.length,+variants.width,+variants.height,+variants.metadata";

async function storeFetch<T>(path: string): Promise<T> {
  if (!publishableKey) throw new Error("Medusa publishable key is missing");
  const response = await fetch(`${baseUrl}${path}`, {
    headers: { "x-publishable-api-key": publishableKey },
    cache: "no-store",
  });
  if (!response.ok) throw new Error(`Medusa Store API returned ${response.status}`);
  return (await response.json()) as T;
}

async function zarRegionId(): Promise<string> {
  const { regions } = await storeFetch<{ regions: MedusaRegion[] }>("/store/regions");
  const region = regions.find((candidate) => candidate.currency_code === "zar");
  if (!region) throw new Error("Medusa ZAR region is missing");
  return region.id;
}

function publicProduct(product: StoreProduct): StoreProduct {
  // Only these presentation fields cross the server-to-client boundary.
  return {
    id: product.id, handle: product.handle, title: product.title,
    description: product.description, thumbnail: product.thumbnail,
    images: (product.images || []).map(({ id, url }) => ({ id, url })),
    options: (product.options || []).map(({ id, title, values }) => ({
      id, title, values: (values || []).map(({ id: valueId, value }) => ({ id: valueId, value })),
    })),
    material: product.material, length: product.length, width: product.width, height: product.height,
    metadata: {
      care_instructions: product.metadata?.care_instructions,
      dimension_unit: product.metadata?.dimension_unit,
      seo_title: product.metadata?.seo_title,
      seo_description: product.metadata?.seo_description,
    },
    categories: (product.categories || []).map(({ id, name, handle }) => ({ id, name, handle })),
    tags: (product.tags || []).map(({ value }) => ({ value })),
    variants: (product.variants || []).map((variant) => ({
      id: variant.id, sku: variant.sku, title: variant.title, thumbnail: variant.thumbnail,
      images: (variant.images || []).map(({ id, url }) => ({ id, url })),
      options: (variant.options || []).map(({ id, value, option_id, option }) => ({ id, value, option_id, option: option ? { id: option.id, title: option.title } : null })),
      material: variant.material, length: variant.length, width: variant.width, height: variant.height,
      inventory_quantity: variant.inventory_quantity,
      calculated_price: variant.calculated_price && {
        calculated_amount: variant.calculated_price.calculated_amount,
        original_amount: variant.calculated_price.original_amount,
        currency_code: variant.calculated_price.currency_code,
        calculated_price: { price_list_type: variant.calculated_price.calculated_price?.price_list_type ?? null },
      },
      metadata: {
        suitable_image_urls: variant.metadata?.suitable_image_urls,
        dimensions_cm: variant.metadata?.dimensions_cm,
        lead_time_days: variant.metadata?.lead_time_days,
        care_instructions: variant.metadata?.care_instructions,
        made_to_order_offer: variant.metadata?.storefront_made_to_order_offer as MadeToOrderOffer | null | undefined,
        swatch_hex: swatchHex(variant.metadata?.swatch_hex),
        sell_multiple: sellCount(variant.metadata?.sell_multiple),
        min_quantity: sellCount(variant.metadata?.min_quantity),
      },
    })),
  };
}

export async function listStoreProducts(): Promise<StoreProduct[]> {
  const regionId = await zarRegionId();
  const products: StoreProduct[] = [];
  for (let offset = 0; ; offset += 100) {
    const query = new URLSearchParams({ region_id: regionId, fields: productFields, limit: "100", offset: String(offset) });
    const page = await storeFetch<{ products: StoreProduct[]; count: number }>(`/store/products?${query}`);
    products.push(...page.products);
    if (page.products.length < 100 || products.length >= page.count) break;
  }
  return products.filter(isPublicProduct).map(publicProduct);
}

const shopCatalogueTtlMs = 15_000;
type ShopCatalogue = { products: Promise<StoreProduct[]>; expiresAt?: number };
let shopCatalogue: ShopCatalogue | undefined;

// The shop routes share a short-lived, anonymous catalogue snapshot. Product
// detail, cart availability and checkout keep reading Medusa independently.
export function listShopProducts(): Promise<StoreProduct[]> {
  if (shopCatalogue && (shopCatalogue.expiresAt === undefined || Date.now() < shopCatalogue.expiresAt)) {
    return shopCatalogue.products;
  }

  const snapshot: ShopCatalogue = { products: listStoreProducts() };
  shopCatalogue = snapshot;
  snapshot.products = snapshot.products.then((products) => {
    snapshot.expiresAt = Date.now() + shopCatalogueTtlMs;
    return products;
  }, (error: unknown) => {
    shopCatalogue = undefined;
    throw error;
  });
  return snapshot.products;
}

function isPublicProduct(product: StoreProduct): boolean {
  return /^firstout-(group-)?[0-9a-f-]{36}$/i.test(product.handle) &&
    (product.status == null || product.status === "published") && product.variants.length > 0;
}

export async function getStoreProduct(slug: string): Promise<StoreProduct | null> {
  const handle = /^[0-9a-f-]{36}$/i.test(slug) ? `firstout-${slug.toLowerCase()}` : slug.toLowerCase();
  if (!/^firstout-(group-)?[0-9a-f-]{36}$/.test(handle)) return null;
  const regionId = await zarRegionId();
  const query = new URLSearchParams({ handle, region_id: regionId, fields: productFields });
  const { products } = await storeFetch<{ products: StoreProduct[] }>(`/store/products?${query}`);
  return products[0] && isPublicProduct(products[0]) ? publicProduct(products[0]) : null;
}

// The most of each variant a shopper can put in the bag. Authoritative cart
// mutations and checkout recheck availability independently.
export async function variantQuantityCaps(productIds: string[]): Promise<Map<string, { cap: number } & SellRules>> {
  if (!productIds.length) return new Map();
  const query = new URLSearchParams({ fields: "id,*variants,+variants.inventory_quantity,+variants.metadata" });
  for (const id of new Set(productIds)) query.append("id", id);
  const { products } = await storeFetch<{ products: StoreProduct[] }>(`/store/products?${query}`);
  return new Map(products.flatMap((product) => product.variants.map((variant) => {
    const stock = variant.inventory_quantity ?? 0;
    const offer = variant.metadata?.storefront_made_to_order_offer;
    const cap = stock > 0 ? stock : offerLive(offer) ? offer.remaining_capacity : 0;
    return [variant.id, { cap, ...sellRules(variant.metadata) }] as const;
  })));
}

export function productPath(product: StoreProduct): string {
  return `/product/${product.handle.replace(/^firstout-(?!group-)/, "")}`;
}

export function lowestPricedVariant(variants: MedusaVariant[]): MedusaVariant | undefined {
  return variants.filter((variant) => variant.calculated_price?.calculated_amount != null)
    .sort((a, b) => a.calculated_price!.calculated_amount - b.calculated_price!.calculated_amount)[0];
}

export function priceLabel(variant?: MedusaVariant): string {
  const amount = variant?.calculated_price?.calculated_amount;
  if (amount == null) return "Price unavailable";
  return formatCustomerPrice(amount, variant?.calculated_price?.currency_code);
}

export function fromPrice(product: StoreProduct): string {
  const prices = product.variants.map((variant) => variant.calculated_price?.calculated_amount).filter((price): price is number => price != null);
  return `${new Set(prices).size > 1 ? "From " : ""}${priceLabel(lowestPricedVariant(product.variants))}`;
}

export type Availability = "in-stock" | "made-to-order";
function variantAvailability(variant: MedusaVariant): Availability | null {
  if ((variant.inventory_quantity ?? 0) > 0) return "in-stock";
  return offerLive(variant.metadata?.made_to_order_offer) ? "made-to-order" : null;
}

// Only a lowercase #rrggbb reaches the page; it is written into a style.
export function swatchHex(value: unknown): string | null {
  return typeof value === "string" && /^#[0-9a-f]{6}$/.test(value) ? value : null;
}

// The pre-sale price, only when a sale price list sets a lower ZAR price.
export function saleOriginal(variant: MedusaVariant): number | null {
  const price = variant.calculated_price;
  if (!price || price.calculated_price?.price_list_type !== "sale" || !isZarCurrency(price.currency_code)) return null;
  return price.original_amount != null && price.original_amount > price.calculated_amount ? price.original_amount : null;
}

export type ListedVariant = {
  id: string;
  name: string;
  /** Option values, such as ["Gold", "160 cm"]. */
  options: string[];
  price: number | null;
  priceLabel: string;
  /** The pre-sale price while a sale price list applies. */
  was: number | null;
  swatch: string | null;
  availability: Availability | null;
  images: string[];
};

// Project only the presentation and selector fields needed by the listing.
export type ListedPiece = Pick<StoreProduct, "id" | "title" | "categories"> & {
  href: string;
  price: number | null;
  priceLabel: string;
  justArrived: boolean;
  variants: ListedVariant[];
};

export function listedPiece(product: StoreProduct): ListedPiece {
  return {
    id: product.id, title: product.title, categories: product.categories, href: productPath(product),
    price: lowestPricedVariant(product.variants)?.calculated_price?.calculated_amount ?? null,
    priceLabel: fromPrice(product),
    justArrived: !!product.tags?.some(({ value }) => value === "just-arrived"),
    variants: product.variants.map((variant) => ({
      id: variant.id, name: variant.title || variant.sku || product.title, options: (variant.options ?? []).map(({ value }) => value),
      price: variant.calculated_price?.calculated_amount ?? null, priceLabel: priceLabel(variant),
      was: saleOriginal(variant), swatch: swatchHex(variant.metadata?.swatch_hex),
      availability: variantAvailability(variant), images: selectedImages(product, variant),
    })),
  };
}

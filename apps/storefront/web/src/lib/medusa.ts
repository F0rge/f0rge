import "server-only";

type MedusaRegion = { id: string; currency_code: string };
export type MedusaImage = { id: string; url: string };
export type MedusaOption = { id: string; title: string; values?: { id: string; value: string }[] };
export type MedusaVariant = {
  id: string;
  sku: string | null;
  title?: string;
  thumbnail?: string | null;
  images?: MedusaImage[] | null;
  options?: { id: string; value: string; option_id?: string | null; option?: { id: string; title: string } | null }[];
  metadata?: { suitable_image_urls?: string[]; lead_time_days?: number } | null;
  material?: string | null;
  length?: number | null;
  width?: number | null;
  height?: number | null;
  inventory_quantity?: number;
  calculated_price?: { calculated_amount: number; currency_code: string };
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
};

const baseUrl = process.env.MEDUSA_BACKEND_URL || "http://localhost:9000";
const publishableKey = process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY;
const productFields = "id,handle,title,description,thumbnail,material,length,width,height,metadata,*images,*options,*options.values,*variants,*variants.images,*variants.options,+variants.inventory_quantity,*variants.calculated_price,+variants.material,+variants.length,+variants.width,+variants.height,+variants.metadata";

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
    variants: (product.variants || []).map((variant) => ({
      id: variant.id, sku: variant.sku, title: variant.title, thumbnail: variant.thumbnail,
      images: (variant.images || []).map(({ id, url }) => ({ id, url })),
      options: (variant.options || []).map(({ id, value, option_id, option }) => ({ id, value, option_id, option: option ? { id: option.id, title: option.title } : null })),
      material: variant.material, length: variant.length, width: variant.width, height: variant.height,
      inventory_quantity: variant.inventory_quantity,
      calculated_price: variant.calculated_price,
      metadata: {
        suitable_image_urls: variant.metadata?.suitable_image_urls,
        lead_time_days: variant.metadata?.lead_time_days,
      },
    })),
  };
}

export async function listStoreProducts(): Promise<StoreProduct[]> {
  const regionId = await zarRegionId();
  const query = new URLSearchParams({ region_id: regionId, fields: productFields, limit: "100" });
  const { products } = await storeFetch<{ products: StoreProduct[] }>(`/store/products?${query}`);
  return products.map(publicProduct);
}

export async function getStoreProduct(slug: string): Promise<StoreProduct | null> {
  const handle = /^[0-9a-f-]{36}$/i.test(slug) ? `firstout-${slug.toLowerCase()}` : slug.toLowerCase();
  if (!/^firstout-(group-)?[0-9a-f-]{36}$/.test(handle)) return null;
  const regionId = await zarRegionId();
  const query = new URLSearchParams({ handle, region_id: regionId, fields: productFields });
  const { products } = await storeFetch<{ products: StoreProduct[] }>(`/store/products?${query}`);
  return products[0] ? publicProduct(products[0]) : null;
}

export function priceLabel(variant?: MedusaVariant): string {
  const amount = variant?.calculated_price?.calculated_amount;
  if (amount == null) return "Price unavailable";
  return new Intl.NumberFormat("en-ZA", { style: "currency", currency: "ZAR" }).format(amount);
}

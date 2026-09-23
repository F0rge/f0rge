import "server-only";

type MedusaRegion = { id: string; currency_code: string };
type MedusaVariant = {
  id: string;
  sku: string | null;
  inventory_quantity?: number;
  calculated_price?: { calculated_amount: number; currency_code: string };
};

export type StoreProduct = {
  id: string;
  handle: string;
  title: string;
  description: string | null;
  variants: MedusaVariant[];
};

const baseUrl = process.env.MEDUSA_BACKEND_URL || "http://localhost:9000";
const publishableKey = process.env.NEXT_PUBLIC_MEDUSA_PUBLISHABLE_KEY;

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

export async function listStoreProducts(): Promise<StoreProduct[]> {
  const regionId = await zarRegionId();
  const query = new URLSearchParams({
    region_id: regionId,
    fields: "id,handle,title,description,*variants,+variants.inventory_quantity,*variants.calculated_price",
    limit: "12",
  });
  const { products } = await storeFetch<{ products: StoreProduct[] }>(
    `/store/products?${query}`,
  );
  return products;
}

export async function getStoreProduct(sourceSkuId: string): Promise<StoreProduct | null> {
  if (!/^[0-9a-f-]{36}$/i.test(sourceSkuId)) return null;
  const handle = `firstout-${sourceSkuId.toLowerCase()}`;
  const regionId = await zarRegionId();
  const query = new URLSearchParams({
    handle,
    region_id: regionId,
    fields: "id,handle,title,description,*variants,+variants.inventory_quantity,*variants.calculated_price",
  });
  const { products } = await storeFetch<{ products: StoreProduct[] }>(
    `/store/products?${query}`,
  );
  return products[0] || null;
}

export function priceLabel(product: StoreProduct): string {
  const amount = product.variants[0]?.calculated_price?.calculated_amount;
  if (amount == null) return "Price unavailable";
  return new Intl.NumberFormat("en-ZA", {
    style: "currency",
    currency: "ZAR",
  }).format(amount);
}

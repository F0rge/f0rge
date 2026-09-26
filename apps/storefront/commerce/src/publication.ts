import type { MedusaContainer } from "@medusajs/framework/types";
import { ContainerRegistrationKeys, MedusaError, ProductStatus } from "@medusajs/framework/utils";
import { isIP } from "node:net";

export type PublicationVariant = {
  id: string;
  sku?: string | null;
  metadata?: Record<string, unknown> | null;
  material?: string | null;
  length?: number | null;
  width?: number | null;
  height?: number | null;
  options?: { value?: string; option?: { title?: string } }[];
  prices?: { amount?: number; currency_code?: string }[];
  images?: { url?: string }[];
};
export type PublicationProduct = {
  id: string;
  external_id?: string | null;
  title?: string | null;
  description?: string | null;
  status?: string;
  metadata?: Record<string, unknown> | null;
  material?: string | null;
  length?: number | null;
  width?: number | null;
  height?: number | null;
  options?: { title?: string }[];
  images?: { url?: string }[];
  sales_channels?: { id: string }[];
};

function usefulText(value: unknown, min: number): boolean {
  return typeof value === "string" && value.trim().length >= min;
}
function positive(value: unknown): boolean {
  return (typeof value === "number" || (typeof value === "string" && value.trim() !== "")) &&
    Number.isFinite(Number(value)) && Number(value) > 0;
}
function suitableImageUrls(value: unknown): unknown[] | null {
  if (Array.isArray(value)) return value;
  if (typeof value !== "string") return null;
  try {
    const parsed: unknown = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : null;
  } catch { return null; }
}
function publicImage(url: unknown): url is string {
  if (typeof url !== "string") return false;
  try {
    const parsed = new URL(url);
    const host = parsed.hostname.toLowerCase().replace(/^\[|\]$/g, "");
    const localDemoImage = process.env.NODE_ENV !== "production" &&
      process.env.STOREFRONT_ALLOW_LOCAL_TEST_IMAGES === "true" &&
      parsed.protocol === "http:" && host === "127.0.0.1" && parsed.port === "3004" &&
      parsed.pathname.startsWith("/demo/") && !parsed.username && !parsed.password && !parsed.search;
    if (localDemoImage) return true;
    const privateName = host === "localhost" || !host.includes(".") ||
      [".localhost", ".local", ".internal", ".lan", ".test", ".invalid"].some((suffix) => host.endsWith(suffix));
    return parsed.protocol === "https:" && !parsed.username && !parsed.password &&
      !parsed.search && !privateName && !isIP(host);
  } catch { return false; }
}

export function publicationProblems(product: PublicationProduct, variant: PublicationVariant, channelId?: string | null): string[] {
  const problems: string[] = [];
  if (product.status !== ProductStatus.PUBLISHED) problems.push("product is not published");
  if (channelId && !product.sales_channels?.some((channel) => channel.id === channelId)) problems.push("product is not in the cart sales channel");
  if (!usefulText(product.title, 3) || !usefulText(variant.sku, 1) ||
      !usefulText(variant.metadata?.source_sku_id, 1)) problems.push("product or SKU identity is incomplete");
  const optionKeys = new Set((product.options || []).map((option) => option.title).filter(Boolean));
  const selected = new Map((variant.options || []).map((option) => [option.option?.title, option.value]));
  if (!optionKeys.size || selected.size !== optionKeys.size ||
      [...optionKeys].some((key) => !usefulText(selected.get(key), 1))) problems.push("variant options are incomplete");
  if (!variant.prices?.some((price) => price.currency_code === "zar" && positive(Number(price.amount))) ||
      variant.metadata?.source_price_includes_tax !== true) problems.push("tax-inclusive ZAR price is missing");
  if (![variant.length ?? product.length, variant.width ?? product.width, variant.height ?? product.height].every(positive) ||
      !["cm", "mm"].includes(String(product.metadata?.dimension_unit || ""))) problems.push("dimensions or dimension unit are missing");
  if (!usefulText(variant.material || product.material, 2) ||
      !usefulText(product.metadata?.care_instructions, 15)) problems.push("material or care instructions are missing");
  if (!usefulText(product.description, 80)) problems.push("product description is too short");
  const gallery = new Set([...(product.images || []), ...(variant.images || [])].map((image) => image.url).filter(publicImage));
  const attested = suitableImageUrls(variant.metadata?.suitable_image_urls);
  if (!attested || new Set(attested).size < 3 ||
      !attested.every((url) => publicImage(url) && gallery.has(url))) {
    problems.push("three public gallery photos attested for this variant are required");
  }
  if (!positive(variant.metadata?.source_available_quantity) && !positive(variant.metadata?.lead_time_days)) {
    problems.push("stock or a positive lead time is required");
  }
  return problems;
}

const publicationFields = [
  "id", "sku", "metadata", "material", "length", "width", "height", "options.value", "options.option.title",
  "prices.amount", "prices.currency_code", "images.url",
  "product.id", "product.external_id", "product.title", "product.description", "product.status",
  "product.metadata", "product.material", "product.length", "product.width", "product.height",
  "product.options.title", "product.images.url", "product.sales_channels.id",
];

export async function assertVariantsPurchasable(container: MedusaContainer, variantIds: string[], channelId?: string | null): Promise<void> {
  if (!variantIds.length) return;
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const { data } = await query.graph({
    entity: "product_variant", fields: publicationFields, filters: { id: variantIds },
  });
  const variants = data as (PublicationVariant & { product?: PublicationProduct })[];
  const found = new Map(variants.map((variant) => [variant.id, variant]));
  for (const id of variantIds) {
    const variant = found.get(id);
    if (!variant?.product) throw new MedusaError(MedusaError.Types.NOT_ALLOWED, `Variant ${id} is unavailable`);
    if (!variant.product.external_id?.startsWith("firstout-")) continue;
    const problems = publicationProblems(variant.product, variant, channelId);
    if (problems.length) throw new MedusaError(MedusaError.Types.NOT_ALLOWED, `Variant ${id} is unavailable: ${problems.join("; ")}`);
  }
}

export async function assertPublishedProductComplete(container: MedusaContainer, productId: string): Promise<void> {
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const { data } = await query.graph({
    entity: "product", filters: { id: productId },
    fields: [
      "id", "external_id", "title", "description", "status", "metadata", "material", "length", "width", "height",
      "options.title", "images.url", "sales_channels.id",
      "variants.id", "variants.sku", "variants.metadata", "variants.material", "variants.length",
      "variants.width", "variants.height", "variants.options.value", "variants.options.option.title",
      "variants.prices.amount", "variants.prices.currency_code", "variants.images.url",
    ],
  });
  const product = data[0] as PublicationProduct & { variants?: PublicationVariant[] } | undefined;
  if (!product || !product.external_id?.startsWith("firstout-") || product.status !== ProductStatus.PUBLISHED) return;
  if (!product.variants?.length) throw new MedusaError(MedusaError.Types.NOT_ALLOWED, "Published product has no variants");
  for (const variant of product.variants) {
    const problems = publicationProblems(product, variant);
    if (problems.length) throw new MedusaError(MedusaError.Types.NOT_ALLOWED, `Variant ${variant.id} cannot be published: ${problems.join("; ")}`);
  }
}

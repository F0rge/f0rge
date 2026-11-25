import { isIP } from "node:net";
import { zarMinorUnits } from "./analytics/money";
import { catalogueIndexable } from "./launch-indexing";
import { offerLive } from "./made-to-order";
import type { MedusaVariant, StoreProduct } from "./medusa";
import { productVariantOptions, selectedImages, variantChoices } from "./product-variants";
import { customerFacingCopy } from "./purchase-feedback";

const CANONICAL_HOMEPAGE = "https://www.daskasas.co.za/";
const MAX_DESCRIPTION_LENGTH = 170;
const SCHEMA = "https://schema.org";
const HTML_ENTITIES: Record<string, string> = {
  amp: "&", nbsp: " ", quot: '"', apos: "'", "#39": "'", "#34": '"',
};
const VARIANT_PROPERTIES: Record<string, "color" | "size" | "material" | "pattern" | undefined> = {
  color: "color", colour: "color", size: "size", material: "material", pattern: "pattern",
  "upholstery colour": "color", "upholstery color": "color", "upholstery material": "material",
  "frame finish": "color", "metal finish": "color",
};

function publicText(value: string | null | undefined): string | null {
  if (!value) return null;
  const plain = value
    .replace(/<!--[^]*?-->|<(script|style)\b[^>]*>[^]*?<\/\1\s*>/gi, " ")
    .replace(/<\/?[a-z][^>]*>/gi, " ")
    .replace(/&(amp|nbsp|quot|apos|#39|#34);/gi, (_, key: string) => HTML_ENTITIES[key.toLowerCase()])
    .replace(/\s+/g, " ")
    .trim();
  return customerFacingCopy(plain);
}

function sentence(value: string): string {
  return /[.!?]$/.test(value) ? value : `${value}.`;
}

function shortDescription(value: string): string {
  if (value.length <= MAX_DESCRIPTION_LENGTH) return value;
  const prefix = value.slice(0, MAX_DESCRIPTION_LENGTH - 1);
  return `${prefix.replace(/\s+\S*$/, "").trimEnd().replace(/[,;:]$/, "")}…`;
}

export function productMetaDescription(product: StoreProduct): string | undefined {
  const name = publicText(product.title);
  if (!name) return undefined;
  const override = publicText(product.metadata?.seo_description);
  const catalogueCopy = publicText(product.description);
  const title = sentence(name).toLowerCase();
  const copy = [override, catalogueCopy].find((candidate) => candidate && sentence(candidate).toLowerCase() !== title);
  if (copy) {
    const description = copy.toLowerCase().includes(name.toLowerCase()) ? copy : `${sentence(name)} ${copy}`;
    return shortDescription(sentence(description));
  }

  const variant = product.variants.length === 1 ? product.variants[0] : undefined;
  const category = publicText(product.categories?.[0]?.name);
  const material = publicText(variant?.material || product.material);
  const sku = publicText(product.variants[0]?.sku);
  const facts = [
    category && `Collection: ${category}`,
    material && `Material: ${material}`,
    sku && `${variant ? "SKU" : "First option SKU"}: ${sku}`,
  ].filter(Boolean).join(" · ");
  return shortDescription(`Explore ${name} at DasKasas.${facts ? ` ${sentence(facts)}` : ""}`);
}

function publicImages(product: StoreProduct, variant: MedusaVariant): string[] {
  return selectedImages(product, variant).flatMap((image) => {
    const relative = image.startsWith("/") && !image.startsWith("//") && !image.includes("\\");
    const url = relative ? URL.parse(image, CANONICAL_HOMEPAGE) : URL.parse(image);
    if (!url || url.protocol !== "https:" || url.username || url.password || url.search || url.hash) return [];
    const host = url.hostname.replace(/^\[|\]$/g, "").replace(/\.$/, "");
    if (!host.includes(".") || isIP(host) || /\.(?:local|localhost|internal|lan|test|invalid)$/.test(host)) return [];
    return [url.href];
  });
}

function variantOffer(variant: MedusaVariant, url: string, sku: string | null) {
  const price = variant.calculated_price;
  if (!sku || !price || price.currency_code?.trim().toUpperCase() !== "ZAR") return undefined;
  const amount = price.calculated_amount;
  const minor = zarMinorUnits(amount);
  if (minor === null || minor <= 0 || minor / 100 !== amount) return undefined;

  const quantity = variant.inventory_quantity;
  const madeToOrder = variant.metadata?.made_to_order_offer;
  let availability: "InStock" | "BackOrder" | "OutOfStock" | undefined;
  if (typeof quantity === "number" && Number.isSafeInteger(quantity) && quantity > 0) {
    availability = "InStock";
  } else if (offerLive(madeToOrder)) {
    const { remaining_capacity: capacity, min_lead_time_days: min, max_lead_time_days: max } = madeToOrder;
    if (Number.isSafeInteger(capacity) && Number.isSafeInteger(min) && min > 0 && Number.isSafeInteger(max) && max >= min) {
      availability = "BackOrder";
    }
  } else if (Number.isSafeInteger(quantity)) {
    availability = "OutOfStock";
  }
  if (!availability) return undefined;
  return { "@type": "Offer", price: amount, priceCurrency: "ZAR", availability: `${SCHEMA}/${availability}`, url };
}

function variantProduct(
  product: StoreProduct, variant: MedusaVariant, name: string, description: string | null,
  canonicalUrl: string, axes: ReturnType<typeof productVariantOptions>,
) {
  const grouped = product.variants.length > 1;
  const url = new URL(canonicalUrl);
  if (grouped) url.searchParams.set("variant", variant.id);
  const choices = variantChoices(variant);
  const options = axes.flatMap(({ id, title }) => {
    const value = publicText(choices[id]);
    return value ? [{ key: VARIANT_PROPERTIES[title.toLowerCase()], name: title, value }] : [];
  });
  const values = options.map(({ value }) => value);
  const properties = Object.fromEntries(options.flatMap(({ key, value }) => key ? [[key, value]] : []));
  const otherOptions = options.flatMap(({ key, name, value }) => key ? [] : [{ "@type": "PropertyValue", name, value }]);
  const sku = publicText(variant.sku);
  const images = publicImages(product, variant);
  const material = publicText(variant.material || product.material);
  const offers = variantOffer(variant, url.href, sku);
  return {
    "@type": "Product",
    "@id": `${url.href}#product`,
    name: values.length ? `${name} – ${values.join(", ")}` : name,
    url: url.href,
    ...(sku ? { sku } : {}),
    ...(description ? { description } : {}),
    ...(images.length ? { image: images } : {}),
    ...(material ? { material } : {}),
    ...properties,
    ...(otherOptions.length ? { additionalProperty: otherOptions } : {}),
    ...(offers ? { offers } : {}),
  };
}

export function productStructuredData(
  product: StoreProduct, path: string, env?: Record<string, string | undefined>,
): string | null {
  if (!path.startsWith("/product/") || !catalogueIndexable(path, env)) return null;

  // Match the product canonical metadata. Next.js inlines the public URL at build time.
  const homepage = URL.parse((env ? env.NEXT_PUBLIC_BASE_URL : process.env.NEXT_PUBLIC_BASE_URL) || "");
  if (!homepage || homepage.href !== CANONICAL_HOMEPAGE) return null;
  const name = publicText(product.title);
  if (!name || !product.variants.length || (product.status != null && product.status !== "published")) return null;

  const canonical = new URL(path, homepage);
  if (canonical.origin !== homepage.origin || !canonical.pathname.startsWith("/product/") || canonical.search || canonical.hash) return null;
  const canonicalUrl = canonical.href;
  const description = publicText(product.description);
  const axes = productVariantOptions(product);
  if (product.variants.length > 1 && !axes.length) return null;
  const products = product.variants.map((variant) => variantProduct(product, variant, name, description, canonicalUrl, axes));
  const variesBy = [...new Set(axes.flatMap(({ title }) => {
    const property = VARIANT_PROPERTIES[title.toLowerCase()];
    return property ? [`${SCHEMA}/${property}`] : [];
  }))];
  const productData = products.length === 1 ? products[0] : {
    "@type": "ProductGroup",
    "@id": `${canonicalUrl}#product-group`,
    name,
    url: canonicalUrl,
    productGroupID: product.id,
    ...(description ? { description } : {}),
    ...(variesBy.length ? { variesBy } : {}),
    hasVariant: products,
  };
  return JSON.stringify({ "@context": SCHEMA, ...productData }).replace(/</g, "\\u003c");
}

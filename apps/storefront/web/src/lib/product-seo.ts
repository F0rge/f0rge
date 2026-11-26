import { isIP } from "node:net";
import { zarMinorUnits } from "./analytics/money";
import { catalogueIndexable } from "./launch-indexing";
import { offerLive } from "./made-to-order";
import type { MedusaVariant, StoreProduct } from "./medusa";
import { productVariantOptions, selectedImages, variantChoices } from "./product-variants";
import { customerFacingCopy } from "./purchase-feedback";
import { sellRules } from "./sell-rules";

const CANONICAL_HOMEPAGE = "https://www.daskasas.co.za/";
const MAX_DESCRIPTION_LENGTH = 170;
const SCHEMA = "https://schema.org";
const HTML_ENTITIES: Record<string, string> = {
  amp: "&", nbsp: " ", quot: '"', apos: "'", "#39": "'", "#34": '"',
};
const VARIANT_PROPERTIES = new Map([
  ["color", "color"], ["colour", "color"], ["size", "size"], ["material", "material"], ["pattern", "pattern"],
  ["upholstery color", "color"], ["upholstery colour", "color"], ["upholstery material", "material"],
]);
const CHOICE_LIST = new Intl.ListFormat("en-ZA", { type: "disjunction" });
const DIMENSION_WORDS = { width: "wide", depth: "deep", height: "high", diameter: "diameter", length: "long" };
type Dimension = keyof typeof DIMENSION_WORDS;

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

function shortDescription(value: string, maxLength = MAX_DESCRIPTION_LENGTH): string {
  if (value.length <= maxLength) return value;
  const prefix = value.slice(0, maxLength - 1);
  return `${prefix.replace(/\s+\S*$/, "").trimEnd().replace(/[,;:]$/, "")}…`;
}

function publishedDimensions(product: StoreProduct, variant?: MedusaVariant) {
  const measured = variant?.metadata?.dimensions_cm;
  const unit = measured ? "cm" : product.metadata?.dimension_unit;
  if (unit !== "cm" && unit !== "mm") return [];
  const measurements: [Dimension, number | null | undefined][] = measured
    ? [["diameter", measured.diameter], ["width", measured.width], ["depth", measured.depth], ["height", measured.height]]
    : [["length", variant?.length ?? product.length], ["width", variant?.width ?? product.width], ["height", variant?.height ?? product.height]];
  const dimensions = measurements.flatMap(([axis, value]) =>
    typeof value === "number" && Number.isFinite(value) && value > 0 ? [{ axis, value, unit }] : []);
  return measured || dimensions.length === measurements.length ? dimensions : [];
}

function sizeDescription(product: StoreProduct): string | null {
  const [first, ...others] = product.variants.map((variant) => publishedDimensions(product, variant));
  const shared = (first ?? publishedDimensions(product)).filter(({ axis, value, unit }) =>
    others.every((measurements) => measurements.some((measurement) =>
      measurement.axis === axis && measurement.value === value && measurement.unit === unit)));
  if (!shared.length) return null;
  if (shared.length === 3 && shared.every(({ axis }) => axis !== "diameter")) {
    return `${shared.map(({ value }) => value).join(" × ")} ${shared[0].unit}`;
  }
  return shared.map(({ axis, value, unit }) => `${value} ${unit} ${DIMENSION_WORDS[axis]}`).join(", ");
}

function optionDescriptions(product: StoreProduct): string[] {
  return productVariantOptions(product).flatMap(({ title, availableValues }) => {
    const label = publicText(title);
    const values = [...new Set(availableValues.flatMap((value) => publicText(value) ?? []))];
    if (!label || values.length < 2) return [];
    const excerpt = CHOICE_LIST.format(values.slice(0, 3));
    return [values.length <= 3 ? `${label}: ${excerpt}` : `${label} options include ${excerpt}`];
  });
}

export function productMetaDescription(product: StoreProduct): string | undefined {
  const name = publicText(product.title);
  if (!name) return undefined;
  const title = sentence(name).toLowerCase();
  const override = publicText(product.metadata?.seo_description);
  if (override && sentence(override).toLowerCase() !== title) {
    const description = override.toLowerCase().includes(name.toLowerCase()) ? override : `${sentence(name)} ${override}`;
    return shortDescription(sentence(description));
  }

  const [firstVariant] = product.variants;
  const category = publicText(product.categories?.[0]?.name);
  const materials = product.variants.map((variant) => publicText(variant.material || product.material));
  const [firstMaterial = publicText(product.material)] = materials;
  const material = materials.every((value) => value === firstMaterial) ? firstMaterial : null;
  const sku = publicText(firstVariant?.sku);
  const size = sizeDescription(product);
  const copy = publicText(product.description);
  // TODO(leo): Add verified finish, material or design details in Firstout for Thera, Carmella and Genevieve,
  // and clarify how Alba and Maya differ beyond their shared dimensions.
  const facts = [
    size && `Dimensions: ${size}`,
    ...optionDescriptions(product),
    material && `Material: ${material}`,
    category && `${category} collection`,
  ];
  const hasCatalogueCopy = copy != null && sentence(copy).toLowerCase() !== title;
  const fallback = facts.some(Boolean) ? sentence(name) : `Explore ${name} at DasKasas.`;
  const lead = hasCatalogueCopy
    ? sentence(copy.toLowerCase().includes(name.toLowerCase()) ? copy : `${sentence(name)} ${copy}`)
    : fallback;
  const skuText = sku && !lead.includes(sku) ? ` SKU ${sku}.` : "";
  const identifier = skuText.length < MAX_DESCRIPTION_LENGTH / 2 ? skuText : "";
  const limit = MAX_DESCRIPTION_LENGTH - identifier.length;
  let description = shortDescription(lead, limit);
  if (!hasCatalogueCopy) {
    for (const fact of facts) {
      if (!fact) continue;
      const extended = `${description} ${sentence(fact)}`;
      if (extended.length <= limit) description = extended;
    }
  }
  return `${description}${identifier}`;
}

export function productPageCopy(product: StoreProduct, variant?: MedusaVariant) {
  const title = product.metadata?.seo_title || product.title;
  const choices = variantChoices(variant);
  const selection = variant ? productVariantOptions(product).flatMap(({ id, title: optionTitle }) => {
    const label = publicText(optionTitle);
    const value = publicText(choices[id]);
    return label && value ? [{ label, value }] : [];
  }) : [];
  if (!selection.length) return { title, description: productMetaDescription(product) };

  const name = publicText(product.title) || title;
  const options = selection.map(({ label, value }) => sentence(`${label}: ${value}`));
  const sku = publicText(variant?.sku);
  return {
    title: `${title} – ${selection.map(({ value }) => value).join(", ")}`,
    description: shortDescription([sentence(name), ...options, ...(sku ? [sentence(`SKU ${sku}`)] : [])].join(" ")),
  };
}

function publicImages(product: StoreProduct, variant: MedusaVariant, canonicalUrl: string): string[] {
  const storefrontOrigin = URL.parse(canonicalUrl)?.origin;
  return selectedImages(product, variant).flatMap((image) => {
    if (image.startsWith("//") || image.includes("\\")) return [];
    const url = image.startsWith("/") ? URL.parse(image, canonicalUrl) : URL.parse(image);
    if (!url || url.protocol !== "https:" || url.username || url.password || url.search || url.hash) return [];
    if (url.origin === storefrontOrigin && url.pathname.startsWith("/demo/")) return [];
    const host = url.hostname.replace(/^\[|\]$/g, "").replace(/\.$/, "");
    if (!host.includes(".") || isIP(host) || /\.(?:local|localhost|internal|lan|test|invalid)$/.test(host)) return [];
    return [url.href];
  });
}

export function productShareImage(
  product: StoreProduct,
  variant?: MedusaVariant,
  baseUrl = process.env.NEXT_PUBLIC_BASE_URL || "http://localhost:3004",
) {
  for (const candidate of variant ? [variant] : product.variants) {
    const [url] = publicImages(product, candidate, baseUrl);
    if (url) return { url, alt: publicText(product.title) || product.title };
  }
}

function offerAvailability(variant: MedusaVariant): "InStock" | "BackOrder" | "OutOfStock" | null {
  const quantity = variant.inventory_quantity;
  if (typeof quantity === "number" && Number.isSafeInteger(quantity) && quantity > 0) return "InStock";
  const madeToOrder = variant.metadata?.made_to_order_offer;
  if (offerLive(madeToOrder)) {
    return Number.isSafeInteger(madeToOrder.remaining_capacity) &&
      Number.isSafeInteger(madeToOrder.min_lead_time_days) && madeToOrder.min_lead_time_days > 0 &&
      Number.isSafeInteger(madeToOrder.max_lead_time_days) && madeToOrder.max_lead_time_days >= madeToOrder.min_lead_time_days
      ? "BackOrder" : null;
  }
  return quantity === 0 ? "OutOfStock" : null;
}

function variantOffer(variant: MedusaVariant, url: string, sku: string | null) {
  const price = variant.calculated_price;
  if (!sku || !price || price.currency_code?.trim().toUpperCase() !== "ZAR") return undefined;
  const amount = price.calculated_amount;
  const minor = zarMinorUnits(amount);
  if (minor === null || minor <= 0 || minor / 100 !== amount) return undefined;

  const availability = offerAvailability(variant);
  if (!availability) return undefined;
  const { minimum } = sellRules(variant.metadata);
  return {
    "@type": "Offer", price: amount, priceCurrency: "ZAR", availability: `${SCHEMA}/${availability}`, url,
    ...(minimum > 1 ? { eligibleQuantity: { "@type": "QuantitativeValue", minValue: minimum } } : {}),
  };
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
    return value ? [{ key: VARIANT_PROPERTIES.get(title.trim().toLowerCase()), name: title, value }] : [];
  });
  const values = options.map(({ value }) => value);
  const properties = Object.fromEntries(options.flatMap(({ key, value }) => key ? [[key, value]] : []));
  const otherOptions = options.flatMap(({ key, name, value }) =>
    key ? [] : [{ "@type": "PropertyValue", name, value }]);
  const sku = publicText(variant.sku);
  const images = publicImages(product, variant, canonicalUrl);
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
  if (canonical.origin !== homepage.origin || canonical.pathname !== path || canonical.search || canonical.hash) return null;
  const canonicalUrl = canonical.href;
  const description = publicText(product.description);
  const axes = productVariantOptions(product);
  if (product.variants.length > 1 && !axes.length) return null;
  const products = product.variants.map((variant) => variantProduct(product, variant, name, description, canonicalUrl, axes));
  const variesBy = [...new Set(axes.flatMap(({ title }) => {
    const property = VARIANT_PROPERTIES.get(title.trim().toLowerCase());
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

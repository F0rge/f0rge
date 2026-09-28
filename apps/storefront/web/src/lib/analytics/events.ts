export type AnalyticsPageKey = "home" | "shop" | "collections" | "product";
export type AnalyticsSurface = "home" | "shop" | "collections";
export type SearchSortOrder = "default" | "price_asc" | "price_desc";

export type StorefrontBrowserEvent =
  | { name: "storefront_page_viewed"; properties: { page_key: AnalyticsPageKey; product_id?: string; utm_source?: string; utm_medium?: string; utm_campaign?: string; referrer_host?: string } }
  | { name: "storefront_product_impressed"; properties: { product_id: string; surface: AnalyticsSurface } }
  | { name: "storefront_product_selected"; properties: { product_id: string; surface: AnalyticsSurface } }
  | { name: "storefront_product_viewed"; properties: { product_id: string } }
  | { name: "storefront_product_media_selected"; properties: { product_id: string; media_index: number } }
  | { name: "storefront_product_variant_selected"; properties: { product_id: string; option_id: string; value_index: number; variant_id?: string } }
  | { name: "storefront_search_results_viewed"; properties: { query_present: boolean; category_id?: string; collection_id?: string; availability: "all" | "in_stock"; price_filter_active: boolean; sort_order: SearchSortOrder; result_count: number } }
  | { name: "storefront_product_attention_summary"; properties: { product_id: string; active_seconds: number; visibility_threshold: "half_visible" } };

export type AnalyticsProperties = Record<string, boolean | number | string>;
export type SanitizedAnalyticsEvent = { name: StorefrontBrowserEvent["name"]; properties: AnalyticsProperties };

/** A provider-neutral sink that can be implemented by a browser or server adapter. */
export interface AnalyticsProvider<Event> {
  capture(event: Event): void;
}

export type BrowserAnalyticsProvider = AnalyticsProvider<StorefrontBrowserEvent>;
export type ServerAnalyticsProvider<Event> = AnalyticsProvider<Event>;

const pageKeys = new Set<AnalyticsPageKey>(["home", "shop", "collections", "product"]);
const surfaces = new Set<AnalyticsSurface>(["home", "shop", "collections"]);
const sortOrders = new Set<SearchSortOrder>(["default", "price_asc", "price_desc"]);

function record(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function safeId(value: unknown): string | null {
  return typeof value === "string" && /^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(value) ? value : null;
}

function safeCampaign(value: unknown): string | null {
  if (typeof value !== "string" || value.length > 64 || !/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(value)) return null;
  return value.toLowerCase();
}

export function sanitizeReferrerHost(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const host = value.toLowerCase().replace(/^www\./, "");
  if (host.length > 253 || !/^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/.test(host)) return null;
  return host;
}

function boundedInteger(value: unknown, min: number, max: number): number | null {
  return typeof value === "number" && Number.isFinite(value) && value >= min && value <= max
    ? Math.floor(value)
    : null;
}

function optionalId(properties: Record<string, unknown>, key: string, target: AnalyticsProperties): boolean {
  if (properties[key] === undefined) return true;
  const value = safeId(properties[key]);
  if (!value) return false;
  target[key] = value;
  return true;
}

function optionalCampaign(properties: Record<string, unknown>, key: string, target: AnalyticsProperties): void {
  const value = safeCampaign(properties[key]);
  if (value) target[key] = value;
}

/** Rebuilds events from a strict allowlist so unexpected caller properties never reach a provider. */
export function sanitizeAnalyticsEvent(input: unknown): SanitizedAnalyticsEvent | null {
  const event = record(input);
  const properties = record(event?.properties);
  if (!event || !properties || typeof event.name !== "string") return null;

  switch (event.name) {
    case "storefront_page_viewed": {
      if (!pageKeys.has(properties.page_key as AnalyticsPageKey)) return null;
      const safe: AnalyticsProperties = { page_key: properties.page_key as string };
      if (!optionalId(properties, "product_id", safe)) return null;
      optionalCampaign(properties, "utm_source", safe);
      optionalCampaign(properties, "utm_medium", safe);
      optionalCampaign(properties, "utm_campaign", safe);
      const referrer = sanitizeReferrerHost(properties.referrer_host);
      if (referrer) safe.referrer_host = referrer;
      return { name: event.name, properties: safe };
    }
    case "storefront_product_impressed":
    case "storefront_product_selected": {
      const productId = safeId(properties.product_id);
      if (!productId || !surfaces.has(properties.surface as AnalyticsSurface)) return null;
      return { name: event.name, properties: { product_id: productId, surface: properties.surface as string } };
    }
    case "storefront_product_viewed": {
      const productId = safeId(properties.product_id);
      return productId ? { name: event.name, properties: { product_id: productId } } : null;
    }
    case "storefront_product_media_selected": {
      const productId = safeId(properties.product_id);
      const mediaIndex = boundedInteger(properties.media_index, 0, 500);
      return productId && mediaIndex !== null
        ? { name: event.name, properties: { product_id: productId, media_index: mediaIndex } }
        : null;
    }
    case "storefront_product_variant_selected": {
      const productId = safeId(properties.product_id);
      const optionId = safeId(properties.option_id);
      const valueIndex = boundedInteger(properties.value_index, 0, 500);
      if (!productId || !optionId || valueIndex === null) return null;
      const safe: AnalyticsProperties = { product_id: productId, option_id: optionId, value_index: valueIndex };
      if (!optionalId(properties, "variant_id", safe)) return null;
      return { name: event.name, properties: safe };
    }
    case "storefront_search_results_viewed": {
      if (typeof properties.query_present !== "boolean") return null;
      const resultCount = boundedInteger(properties.result_count, 0, 100_000);
      if (resultCount === null) return null;
      const safe: AnalyticsProperties = {
        query_present: properties.query_present,
        availability: properties.availability === "in_stock" ? "in_stock" : "all",
        price_filter_active: properties.price_filter_active === true,
        sort_order: sortOrders.has(properties.sort_order as SearchSortOrder) ? properties.sort_order as string : "default",
        result_count: resultCount,
      };
      if (!optionalId(properties, "category_id", safe) || !optionalId(properties, "collection_id", safe)) return null;
      return { name: event.name, properties: safe };
    }
    case "storefront_product_attention_summary": {
      const productId = safeId(properties.product_id);
      const activeSeconds = boundedInteger(properties.active_seconds, 1, 86_400);
      return productId && activeSeconds !== null
        ? { name: event.name, properties: { product_id: productId, active_seconds: activeSeconds, visibility_threshold: "half_visible" } }
        : null;
    }
    default:
      return null;
  }
}

export function analyticsPageForPathname(pathname: string): { pageKey: AnalyticsPageKey; productId?: string } | null {
  if (pathname === "/") return { pageKey: "home" };
  if (pathname === "/shop") return { pageKey: "shop" };
  if (pathname === "/collections") return { pageKey: "collections" };
  const match = /^\/product\/(group-)?([0-9a-f-]{36})\/?$/i.exec(pathname);
  return match ? { pageKey: "product", productId: `${match[1] || ""}${match[2].toLowerCase()}` } : null;
}

export function analyticsSurfaceForPathname(pathname: string): AnalyticsSurface | null {
  if (pathname === "/") return "home";
  if (pathname === "/shop") return "shop";
  if (pathname === "/collections") return "collections";
  return null;
}

export type AcquisitionProperties = { utm_source?: string; utm_medium?: string; utm_campaign?: string; referrer_host?: string };

export function acquisitionProperties(search: string, referrer: string): AcquisitionProperties {
  const safe: AnalyticsProperties = {};
  try {
    const params = new URLSearchParams(search);
    for (const key of ["utm_source", "utm_medium", "utm_campaign"] as const) {
      const value = safeCampaign(params.get(key));
      if (value) safe[key] = value;
    }
  } catch { /* Invalid location input is ignored. */ }
  try {
    const host = sanitizeReferrerHost(new URL(referrer).hostname);
    if (host) safe.referrer_host = host;
  } catch { /* A missing or malformed referrer is not a measurement failure. */ }
  return safe;
}

import { assessLaunchPack, type LaunchPackFinding } from "./launch-pack";

export type StockedPromise = { kind: "stocked"; quantity: number };
export type MadeToOrderPromise = {
  kind: "made_to_order";
  allowance: number;
  min_lead_time_days: number;
  max_lead_time_days: number;
  expires_at: string;
};

export type LoadedVariant = {
  sku: string;
  product_group_id: string;
  option_key: string;
  mapping_id: string;
  published: boolean;
  price_zar_incl_vat: string;
  photo_urls: string[];
  promise: StockedPromise | MadeToOrderPromise;
};

export type PaidOrderLine = { sku: string; quantity: number; amount_cents: number };
export type PaidOrder = { id: string; paid: true; lines: PaidOrderLine[] };

export type LaunchShelf = {
  variants: LoadedVariant[];
  orders: PaidOrder[];
};

export type LoadResult = {
  shelf: LaunchShelf;
  loaded: boolean;
  public_selling: false;
  findings: LaunchPackFinding[];
};

export type CustomerPolicies = {
  legal_name: string;
  trading_name: string;
  contact_address: string;
  support_mailbox: string;
  delivery: string;
  collection_location: string;
  collection_instructions: string;
  gauteng_zones: { name: string; rate_zar_incl_vat: string }[];
  cancellation_returns_refund: string;
  privacy: string;
  information_officer_name: string;
  information_officer_responsibilities: string;
  paia_baseline: string;
  collector_skin: string;
  distinguishes_standard_made_to_order_from_bespoke: true;
};

const NOT_PUBLISHED = "This piece is not published.";

function copyVariant(variant: LoadedVariant): LoadedVariant {
  return {
    ...variant,
    photo_urls: [...variant.photo_urls],
    promise: { ...variant.promise },
  };
}

function copyShelf(shelf: LaunchShelf): LaunchShelf {
  return {
    variants: shelf.variants.map(copyVariant),
    orders: shelf.orders.map((order) => ({
      ...order,
      lines: order.lines.map((line) => ({ ...line })),
    })),
  };
}

function record(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function optionKey(options: unknown): string {
  const item = record(options);
  if (!item) return "";
  return Object.entries(item)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join(", ");
}

function promiseFrom(value: unknown): StockedPromise | MadeToOrderPromise {
  const availability = record(value);
  if (availability?.kind === "made_to_order") {
    return {
      kind: "made_to_order",
      allowance: Number(availability.allowance),
      min_lead_time_days: Number(availability.min_lead_time_days),
      max_lead_time_days: Number(availability.max_lead_time_days),
      expires_at: String(availability.expires_at),
    };
  }
  return { kind: "stocked", quantity: Number(availability?.quantity) };
}

function variantsFrom(pack: unknown): LoadedVariant[] {
  const root = record(pack);
  const catalogue = root ? record(root.catalogue) : null;
  const variants = catalogue && Array.isArray(catalogue.variants) ? catalogue.variants : [];
  return variants.map((item) => {
    const variant = record(item);
    const sku = String(variant?.sku || "").trim();
    const productGroupId = String(variant?.product_group_id || "").trim();
    const photos = Array.isArray(variant?.licensed_photos) ? variant.licensed_photos : [];
    return {
      sku,
      product_group_id: productGroupId,
      option_key: optionKey(variant?.options),
      mapping_id: `launch:${productGroupId}:${sku}`,
      published: true,
      price_zar_incl_vat: String(variant?.price_zar_incl_vat || ""),
      photo_urls: photos.flatMap((photo) => {
        const entry = record(photo);
        return entry && typeof entry.url === "string" ? [entry.url] : [];
      }),
      promise: promiseFrom(variant?.availability),
    };
  });
}

export function loadApprovedLaunchPack(shelf: LaunchShelf, pack: unknown, now: Date = new Date()): LoadResult {
  const assessment = assessLaunchPack(pack, now);
  if (!assessment.ready) {
    return { shelf: copyShelf(shelf), loaded: false, public_selling: false, findings: assessment.findings };
  }
  const previous = new Map(shelf.variants.map((variant) => [variant.sku, variant]));
  const seen = new Set<string>();
  const variants = variantsFrom(pack).map((variant) => {
    seen.add(variant.sku);
    const prior = previous.get(variant.sku);
    return prior ? { ...variant, mapping_id: prior.mapping_id } : variant;
  });
  shelf.variants.forEach((variant) => {
    if (!seen.has(variant.sku)) variants.push({ ...copyVariant(variant), published: false });
  });
  return {
    shelf: { variants, orders: copyShelf(shelf).orders },
    loaded: true,
    public_selling: false,
    findings: [],
  };
}

export function summarizeLaunchLoad(pack: unknown, now: Date = new Date()): {
  loaded: boolean;
  public_selling: false;
  published_variants: number;
  findings: LaunchPackFinding[];
} {
  const result = loadApprovedLaunchPack({ variants: [], orders: [] }, pack, now);
  return {
    loaded: result.loaded,
    public_selling: false,
    published_variants: result.shelf.variants.filter((variant) => variant.published).length,
    findings: result.findings,
  };
}

export function directPurchase(shelf: LaunchShelf, sku: string): { allowed: false; reason: string } | { allowed: true; mapping_id: string } {
  const variant = shelf.variants.find((item) => item.sku === sku && item.published);
  if (!variant) return { allowed: false, reason: NOT_PUBLISHED };
  return { allowed: true, mapping_id: variant.mapping_id };
}

export function publishedCustomerPolicies(pack: unknown, now: Date = new Date()): CustomerPolicies | null {
  if (!assessLaunchPack(pack, now).ready) return null;
  const root = record(pack);
  const business = record(root?.business);
  const fulfilment = record(root?.fulfilment);
  const collection = record(fulfilment?.collection);
  const policies = record(root?.policies);
  const zones = Array.isArray(fulfilment?.gauteng_zones) ? fulfilment.gauteng_zones : [];
  if (!business || !collection || !policies) return null;
  return {
    legal_name: String(business.legal_name),
    trading_name: String(business.trading_name),
    contact_address: String(business.contact_address),
    support_mailbox: String(business.support_mailbox),
    delivery: String(policies.delivery),
    collection_location: String(collection.location),
    collection_instructions: String(collection.instructions),
    gauteng_zones: zones.flatMap((zone) => {
      const item = record(zone);
      if (!item) return [];
      return [{ name: String(item.name), rate_zar_incl_vat: String(item.rate_zar_incl_vat) }];
    }),
    cancellation_returns_refund: String(policies.cancellation_returns_refund),
    privacy: String(policies.privacy),
    information_officer_name: String(policies.information_officer_name),
    information_officer_responsibilities: String(policies.information_officer_responsibilities),
    paia_baseline: String(policies.paia_baseline),
    collector_skin: String(policies.collector_skin),
    distinguishes_standard_made_to_order_from_bespoke: true,
  };
}

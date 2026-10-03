import { opaqueAnalyticsId } from "./attribution";
import { sanitizeServerEvent } from "./commerce-events";
import { sanitizeAnalyticsEvent, type SanitizedAnalyticsEvent } from "./events";
import { CONSENTED_MEASUREMENT_DISCLAIMER, CONSENTED_MEASUREMENT_SCOPE, type ConsentedReportRow } from "./reports";

export const DASHBOARD_IDS = [
  "store_health",
  "acquisition",
  "product_performance",
  "purchase_funnel",
  "search_merchandising",
  "friction_quality",
  "accounts",
] as const;

export type DashboardId = (typeof DASHBOARD_IDS)[number];

export type CommerceDashboard = {
  id: DashboardId;
  title: string;
  scope: typeof CONSENTED_MEASUREMENT_SCOPE;
  disclaimer: string;
  denominators: "matching_consent_scope";
  revenue_authority: "server_confirmed_orders_and_refunds" | "not_revenue";
  rows: ConsentedReportRow[];
};

export type MeasuredCapture = {
  event?: string;
  name?: string;
  distinct_id?: string;
  properties?: Record<string, unknown>;
};

type LinkedEvent = SanitizedAnalyticsEvent & { distinctId: string; anonymousId: string | null };

const FUNNEL_STEPS = ["catalogue", "product", "cart", "checkout", "shipping", "payment", "order"] as const;

function measured(input: MeasuredCapture): LinkedEvent | null {
  const name = input.name || input.event;
  const sanitized = sanitizeAnalyticsEvent({ name, properties: input.properties || {} })
    || sanitizeServerEvent({ name, properties: input.properties || {} });
  if (!sanitized) return null;
  const distinctId = opaqueAnalyticsId(input.distinct_id) || opaqueAnalyticsId(sanitized.properties.anonymous_id) || "";
  const anonymousId = opaqueAnalyticsId(sanitized.properties.anonymous_id);
  return { ...sanitized, distinctId, anonymousId };
}

function canonicalId(event: LinkedEvent, alias: Map<string, string>): string {
  if (event.anonymousId && event.distinctId) alias.set(event.anonymousId, event.distinctId);
  return alias.get(event.distinctId) || event.distinctId;
}

function shell(id: DashboardId, title: string, rows: ConsentedReportRow[], revenue: CommerceDashboard["revenue_authority"]): CommerceDashboard {
  return {
    id,
    title,
    scope: CONSENTED_MEASUREMENT_SCOPE,
    disclaimer: CONSENTED_MEASUREMENT_DISCLAIMER,
    denominators: "matching_consent_scope",
    revenue_authority: revenue,
    rows,
  };
}

function visitorsFor(events: LinkedEvent[], alias: Map<string, string>, predicate: (event: LinkedEvent) => boolean): Set<string> {
  const ids = new Set<string>();
  for (const event of events) {
    if (!predicate(event)) continue;
    const id = canonicalId(event, alias);
    if (id) ids.add(id);
  }
  return ids;
}

/** Seven saved dashboard definitions. Revenue counts only server-confirmed orders and refunds. */
export function consentedCommerceDashboards(events: MeasuredCapture[]): Record<DashboardId, CommerceDashboard> {
  const linked = events.flatMap((event) => {
    const safe = measured(event);
    return safe ? [safe] : [];
  });
  const alias = new Map<string, string>();
  for (const event of linked) canonicalId(event, alias);

  const orders = linked.filter((event) => event.name === "storefront_order_completed");
  const refunds = linked.filter((event) => event.name === "storefront_order_refunded");
  const revenueMinor = orders.reduce((sum, event) => sum + Number(event.properties.value_minor || 0), 0);
  const refundedMinor = refunds.reduce((sum, event) => sum + Number(event.properties.refund_minor || 0), 0);
  const visitorIds = visitorsFor(linked, alias, (event) => event.name === "storefront_page_viewed" || event.name === "storefront_order_completed");
  const orderVisitors = visitorsFor(orders, alias, () => true);
  const net = revenueMinor - refundedMinor;

  const acquisition = new Map<string, ConsentedReportRow>();
  const campaignByVisitor = new Map<string, { utm_source: string; utm_campaign: string }>();
  for (const event of linked) {
    if (event.name !== "storefront_page_viewed") continue;
    const id = canonicalId(event, alias);
    if (!id || campaignByVisitor.has(id)) continue;
    campaignByVisitor.set(id, {
      utm_source: String(event.properties.utm_source || "(none)"),
      utm_campaign: String(event.properties.utm_campaign || "(none)"),
    });
  }
  for (const campaign of campaignByVisitor.values()) {
    const key = `${campaign.utm_source}|${campaign.utm_campaign}`;
    const row = acquisition.get(key) || { utm_source: campaign.utm_source, utm_campaign: campaign.utm_campaign, visitors: 0, orders: 0, revenue_minor: 0 };
    row.visitors = Number(row.visitors) + 1;
    acquisition.set(key, row);
  }
  for (const event of orders) {
    const campaign = campaignByVisitor.get(canonicalId(event, alias)) || { utm_source: "(none)", utm_campaign: "(none)" };
    const key = `${campaign.utm_source}|${campaign.utm_campaign}`;
    const row = acquisition.get(key) || { utm_source: campaign.utm_source, utm_campaign: campaign.utm_campaign, visitors: 0, orders: 0, revenue_minor: 0 };
    row.orders = Number(row.orders) + 1;
    row.revenue_minor = Number(row.revenue_minor) + Number(event.properties.value_minor || 0);
    acquisition.set(key, row);
  }

  const products = new Map<string, ConsentedReportRow>();
  const seenViewers = new Set<string>();
  function productRow(productId: string): ConsentedReportRow {
    return products.get(productId) || { product_id: productId, viewers: 0, active_seconds: 0, selections: 0, add_to_cart: 0 };
  }
  for (const event of linked) {
    const productId = typeof event.properties.product_id === "string" ? event.properties.product_id : "";
    if (!productId) continue;
    const row = productRow(productId);
    if (event.name === "storefront_product_viewed") {
      const viewerKey = `${productId}:${canonicalId(event, alias) || "anonymous"}`;
      if (!seenViewers.has(viewerKey)) {
        seenViewers.add(viewerKey);
        row.viewers = Number(row.viewers) + 1;
      }
    }
    if (event.name === "storefront_product_attention_summary") row.active_seconds = Number(row.active_seconds) + Number(event.properties.active_seconds || 0);
    if (event.name === "storefront_product_selected") row.selections = Number(row.selections) + 1;
    if (event.name === "storefront_cart_item_added") row.add_to_cart = Number(row.add_to_cart) + 1;
    products.set(productId, row);
  }

  const funnelVisitors = FUNNEL_STEPS.map((step) => {
    const ids = visitorsFor(linked, alias, (event) => {
      if (step === "catalogue") return event.name === "storefront_page_viewed" || event.name === "storefront_product_impressed";
      if (step === "product") return event.name === "storefront_product_viewed";
      if (step === "cart") return event.name === "storefront_cart_viewed" || event.name === "storefront_cart_item_added";
      if (step === "checkout") return event.name === "storefront_checkout_started";
      if (step === "shipping") return event.name === "storefront_shipping_method_selected";
      if (step === "payment") return event.name === "storefront_checkout_step_completed" && event.properties.step === "payment";
      return event.name === "storefront_order_completed";
    });
    return { step, visitors: ids.size };
  });

  const searchVisitors = visitorsFor(linked, alias, (event) => event.name === "storefront_search_results_viewed");
  const emptySearch = linked.filter((event) => event.name === "storefront_search_results_viewed" && Number(event.properties.result_count) === 0).length;
  const searchOrders = orders.filter((event) => searchVisitors.has(canonicalId(event, alias))).length;

  const friction = new Map<string, number>();
  for (const event of linked) {
    if (event.name !== "storefront_friction_noted" && event.name !== "storefront_payment_failed") continue;
    const kind = String(event.properties.kind || event.properties.reason_family || "(none)");
    friction.set(kind, (friction.get(kind) || 0) + 1);
  }

  const accountMix = new Map<string, number>();
  for (const event of orders) {
    const customerType = String(event.properties.customer_type || "guest");
    accountMix.set(customerType, (accountMix.get(customerType) || 0) + 1);
  }

  return {
    store_health: shell("store_health", "Store health", [
      { metric: "visitors", value: visitorIds.size },
      { metric: "orders", value: orderVisitors.size },
      { metric: "revenue_minor", value: revenueMinor },
      { metric: "refunded_minor", value: refundedMinor },
      { metric: "net_revenue_minor", value: net },
      { metric: "average_order_value_minor", value: orders.length ? Math.round(revenueMinor / orders.length) : 0 },
      { metric: "revenue_per_visitor_minor", value: visitorIds.size ? Math.round(net / visitorIds.size) : 0 },
    ], "server_confirmed_orders_and_refunds"),
    acquisition: shell("acquisition", "Acquisition", [...acquisition.values()], "server_confirmed_orders_and_refunds"),
    product_performance: shell("product_performance", "Product performance", [...products.values()], "not_revenue"),
    purchase_funnel: shell("purchase_funnel", "Purchase funnel", funnelVisitors, "not_revenue"),
    search_merchandising: shell("search_merchandising", "Search and merchandising", [
      { metric: "searches", value: linked.filter((event) => event.name === "storefront_search_results_viewed").length },
      { metric: "empty_searches", value: emptySearch },
      { metric: "orders_after_search", value: searchOrders },
    ], "server_confirmed_orders_and_refunds"),
    friction_quality: shell("friction_quality", "Friction and quality", [
      { metric: "replay_sample_rate", value: 0.1 },
      ...[...friction.entries()].map(([kind, value]) => ({ kind, value })),
    ], "not_revenue"),
    accounts: shell("accounts", "Accounts", [
      { metric: "account_created", value: linked.filter((event) => event.name === "storefront_account_created").length },
      { metric: "account_signed_in", value: linked.filter((event) => event.name === "storefront_account_signed_in").length },
      ...[...accountMix.entries()].map(([customer_type, orders_count]) => ({ customer_type, orders: orders_count })),
    ], "not_revenue"),
  };
}

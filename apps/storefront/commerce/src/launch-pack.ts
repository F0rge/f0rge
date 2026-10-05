import { isIP } from "node:net";

export type LaunchPackFinding = {
  section: "business_identity" | "catalogue" | "availability_and_fulfilment" | "policies_and_skin" | "provisioning";
  code: string;
  detail: string;
};

export type LaunchPackAssessment = {
  ready: boolean;
  findings: LaunchPackFinding[];
};

const ABSENT: LaunchPackFinding[] = [
  {
    section: "business_identity",
    code: "business_identity_unconfirmed",
    detail: "Owner has not confirmed the legal entity, trading name, contact address, VAT position, support mailbox, daily operator, or escalation availability.",
  },
  {
    section: "catalogue",
    code: "catalogue_not_approved",
    detail: "Owner has not approved a 30 to 80 variant catalogue with SKU mapping, VAT-inclusive ZAR prices, dimensions, material, care, copy, and licensed photos.",
  },
  {
    section: "availability_and_fulfilment",
    code: "availability_unconfirmed",
    detail: "Owner has not supplied physical stock or finite made-to-order allowances, Gauteng delivery, collection instructions, or mixed-cart promise approval.",
  },
  {
    section: "policies_and_skin",
    code: "policies_unreviewed",
    detail: "Owner has not supplied reviewed delivery, cancellation, privacy, and PAIA content, or selected a final Collector D font and palette.",
  },
  {
    section: "provisioning",
    code: "provisioning_incomplete",
    detail: "Secure provisioning checklist for Clerk, Peach, email, PostHog, Railway, and the temporary hostname is incomplete.",
  },
];

const RESERVED_MAIL_DOMAINS = [".example", ".test", ".invalid", ".localhost", ".local"];

function record(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function text(value: unknown, min: number): boolean {
  return typeof value === "string" && value.trim().length >= min;
}

function dedicatedMailbox(value: unknown): boolean {
  if (typeof value !== "string") return false;
  const mailbox = value.trim().toLowerCase();
  const at = mailbox.lastIndexOf("@");
  if (at < 1 || at !== mailbox.indexOf("@") || mailbox.endsWith(".")) return false;
  const domain = mailbox.slice(at + 1);
  if (!domain.includes(".") || domain.includes(" ")) return false;
  return !RESERVED_MAIL_DOMAINS.some((suffix) => domain === suffix.slice(1) || domain.endsWith(suffix));
}

function softwareName(value: unknown): boolean {
  return typeof value === "string" && value.trim().toLowerCase() === "firstout";
}

function businessConfirmed(value: unknown): boolean {
  const business = record(value);
  if (!business) return false;
  if (softwareName(business.legal_name) || softwareName(business.trading_name)) return false;
  const vatKnown = business.vat_registered === false ||
    (business.vat_registered === true && typeof business.vat_number === "string" && /^\d{10}$/.test(business.vat_number));
  return text(business.legal_name, 3) && text(business.trading_name, 2) && text(business.contact_address, 12) &&
    vatKnown && dedicatedMailbox(business.support_mailbox) && text(business.daily_operator_name, 3) &&
    text(business.escalation_availability, 12) && text(business.confirmed_by, 3) &&
    typeof business.confirmed_on === "string" && /^\d{4}-\d{2}-\d{2}$/.test(business.confirmed_on);
}

function positive(value: unknown): boolean {
  return typeof value === "number" && Number.isFinite(value) && value > 0;
}

function money(value: unknown): boolean {
  return typeof value === "string" && /^\d+\.\d{2}$/.test(value) && Number(value) > 0;
}

function publicHttps(value: unknown): value is string {
  if (typeof value !== "string") return false;
  try {
    const parsed = new URL(value);
    const host = parsed.hostname.toLowerCase().replace(/^\[|\]$/g, "");
    const privateName = host === "localhost" || !host.includes(".") ||
      [".localhost", ".local", ".internal", ".lan", ".test", ".invalid"].some((suffix) => host.endsWith(suffix));
    return parsed.protocol === "https:" && !parsed.username && !parsed.password && !parsed.search &&
      !privateName && !isIP(host);
  } catch {
    return false;
  }
}

function catalogueFinding(detail: string): LaunchPackFinding {
  return { section: "catalogue", code: "catalogue_not_approved", detail };
}

function variantProblems(value: unknown, index: number): string[] {
  const variant = record(value);
  const sku = variant && typeof variant.sku === "string" && variant.sku.trim() ? variant.sku.trim() : `variant ${index + 1}`;
  if (!variant) return [`${sku} is not a variant record.`];
  const problems: string[] = [];
  const options = record(variant.options);
  const optionValues = options ? Object.values(options).filter((option) => text(option, 1)) : [];
  if (!text(variant.sku, 1) || !text(variant.product_group_id, 1) || optionValues.length === 0 ||
      !money(variant.price_zar_incl_vat) || !positive(variant.length_cm) || !positive(variant.width_cm) ||
      !positive(variant.height_cm) || !text(variant.material, 2) || !text(variant.care, 15) || !text(variant.copy, 80)) {
    problems.push(`SKU ${sku} is missing identity, VAT-inclusive ZAR price, dimensions, material, care, or copy.`);
  }
  const photos = Array.isArray(variant.licensed_photos) ? variant.licensed_photos : [];
  const licensed = photos.filter((photo) => {
    const item = record(photo);
    return !!item && item.license === "owner_licensed" && publicHttps(item.url);
  }).map((photo) => (record(photo) as { url: string }).url);
  if (new Set(licensed).size < 3) problems.push(`SKU ${sku} needs at least three licensed photos of its own finish.`);
  if (!Array.isArray(variant.wrong_finish_assets)) {
    problems.push(`SKU ${sku} has no wrong-finish review.`);
  } else {
    const flagged = variant.wrong_finish_assets.flatMap((asset) => {
      const item = record(asset);
      return item && typeof item.url === "string" ? [item.url] : [];
    });
    if (flagged.some((url) => licensed.includes(url))) {
      problems.push(`SKU ${sku} lists a wrong-finish asset as a suitable photo.`);
    }
  }
  return problems;
}

function whole(value: unknown, min: number): boolean {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= min;
}

function availabilityDetail(value: unknown, sku: string, now: Date): string | null {
  const availability = record(value);
  if (!availability || (availability.kind !== "stocked" && availability.kind !== "made_to_order")) {
    return `SKU ${sku} has no physical stock or made-to-order allowance.`;
  }
  if (availability.kind === "stocked") {
    return whole(availability.quantity, 1) ? null : `SKU ${sku} physical stock must be a finite quantity above zero.`;
  }
  const expires = typeof availability.expires_at === "string" ? Date.parse(availability.expires_at) : Number.NaN;
  const lead = whole(availability.min_lead_time_days, 1) && whole(availability.max_lead_time_days, 1) &&
    Number(availability.max_lead_time_days) >= Number(availability.min_lead_time_days);
  if (!whole(availability.allowance, 1) || !lead || !Number.isFinite(expires) || expires <= now.getTime()) {
    return `SKU ${sku} made-to-order allowance is missing, exhausted, or expired.`;
  }
  return null;
}

function fulfilmentFinding(detail: string): LaunchPackFinding {
  return { section: "availability_and_fulfilment", code: "availability_unconfirmed", detail };
}

function fulfilmentFindings(root: Record<string, unknown>, now: Date): LaunchPackFinding[] {
  if (!("fulfilment" in root)) return [ABSENT[2]];
  const fulfilment = record(root.fulfilment);
  const findings: LaunchPackFinding[] = [];
  const catalogue = record(root.catalogue);
  const variants = catalogue && Array.isArray(catalogue.variants) ? catalogue.variants : [];
  if (!catalogue || variants.length === 0) {
    findings.push(fulfilmentFinding("Availability cannot be confirmed without catalogue variants."));
  }
  variants.forEach((item, index) => {
    const variant = record(item);
    const sku = variant && typeof variant.sku === "string" && variant.sku.trim() ? variant.sku.trim() : `variant ${index + 1}`;
    const detail = availabilityDetail(variant ? variant.availability : null, sku, now);
    if (detail) findings.push(fulfilmentFinding(detail));
  });
  if (!fulfilment || !text(fulfilment.approved_by, 3) ||
      typeof fulfilment.approved_on !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(fulfilment.approved_on)) {
    findings.push(fulfilmentFinding("Fulfilment inputs have no recorded owner approval."));
  }
  const zones = fulfilment && Array.isArray(fulfilment.gauteng_zones) ? fulfilment.gauteng_zones : [];
  const zonesOk = zones.length > 0 && zones.every((zone) => {
    const item = record(zone);
    return !!item && text(item.name, 3) && money(item.rate_zar_incl_vat);
  });
  if (!zonesOk) findings.push(fulfilmentFinding("Gauteng delivery zones and VAT-inclusive rates are missing."));
  const collection = fulfilment ? record(fulfilment.collection) : null;
  if (!collection || !text(collection.location, 8) || !text(collection.instructions, 20)) {
    findings.push(fulfilmentFinding("Collection location and instructions are missing."));
  }
  const mixed = fulfilment ? record(fulfilment.mixed_cart) : null;
  if (!mixed || mixed.promise !== "single_promise_slowest_line" || mixed.approved !== true) {
    findings.push(fulfilmentFinding("The mixed-cart promise is not approved."));
  }
  return findings;
}

export const COLLECTOR_SKINS = [
  "Oxblood / citron",
  "Ultramarine / shell",
  "Forest / bone",
  "Terracotta / chalk",
  "Ink / saffron",
  "Aubergine / blush",
  "Cobalt / ice",
  "Moss / sand",
  "Charcoal / copper",
  "Petrol / stone",
] as const;

function policyFinding(detail: string): LaunchPackFinding {
  return { section: "policies_and_skin", code: "policies_unreviewed", detail };
}

function mentions(value: unknown, phrase: string): boolean {
  return typeof value === "string" && value.toLowerCase().replace(/-/g, " ").includes(phrase);
}

const PROVISIONING_CHANNELS = ["clerk", "peach", "email", "posthog", "railway", "temporary_hostname"];
const SECRET_KEY = /password|secret|token|api[_-]?key|private[_-]?key|credential|authorization/i;
const SECRET_VALUE = /sk_(?:live|test)_|pk_(?:live|test)_|-----BEGIN |whsec_|Bearer /;
const CUSTOMER_KEY = /^(customers|customer_export|orders)$/;

function walkPack(value: unknown, hit: { secret: boolean; customers: boolean }): void {
  if (typeof value === "string") {
    if (SECRET_VALUE.test(value)) hit.secret = true;
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((item) => walkPack(item, hit));
    return;
  }
  const item = record(value);
  if (!item) return;
  Object.entries(item).forEach(([key, child]) => {
    if (SECRET_KEY.test(key)) hit.secret = true;
    if (CUSTOMER_KEY.test(key)) hit.customers = true;
    walkPack(child, hit);
  });
}

function provisioningFinding(detail: string): LaunchPackFinding {
  return { section: "provisioning", code: "provisioning_incomplete", detail };
}

function provisioningFindings(value: unknown): LaunchPackFinding[] {
  const provisioning = record(value);
  if (!provisioning) return [ABSENT[4]];
  const findings: LaunchPackFinding[] = [];
  if (!text(provisioning.checked_by, 3) || typeof provisioning.checked_on !== "string" ||
      !/^\d{4}-\d{2}-\d{2}$/.test(provisioning.checked_on)) {
    findings.push(provisioningFinding("The provisioning checklist has no recorded checker."));
  }
  const channels = Array.isArray(provisioning.channels) ? provisioning.channels : [];
  PROVISIONING_CHANNELS.forEach((name) => {
    const channel = channels.map(record).find((item) => item?.channel === name);
    if (!channel) {
      findings.push(provisioningFinding(`${name} is missing from the provisioning checklist.`));
      return;
    }
    const remaining = typeof channel.remaining_onboarding === "string" ? channel.remaining_onboarding.trim() : "";
    const accessKnown = typeof channel.authorized_access === "boolean" && typeof channel.test_and_live_separated === "boolean";
    if (!accessKnown || remaining.length < 4) {
      findings.push(provisioningFinding(`${name} does not identify access, test and live separation, and remaining onboarding.`));
      return;
    }
    if ((channel.authorized_access === false || channel.test_and_live_separated === false) && remaining.toLowerCase() === "none") {
      findings.push(provisioningFinding(`${name} still has outstanding access or separation work.`));
    }
  });
  return findings;
}

function policyFindings(value: unknown): LaunchPackFinding[] {
  const policies = record(value);
  if (!policies) return [ABSENT[3]];
  const findings: LaunchPackFinding[] = [];
  if (!text(policies.reviewed_by, 3) || typeof policies.reviewed_on !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(policies.reviewed_on)) {
    findings.push(policyFinding("Delivery, returns, and privacy content has no recorded owner review."));
  }
  if (!text(policies.delivery, 80)) findings.push(policyFinding("Reviewed delivery content is missing."));
  if (!text(policies.cancellation_returns_refund, 80) || !mentions(policies.cancellation_returns_refund, "made to order") ||
      !mentions(policies.cancellation_returns_refund, "bespoke")) {
    findings.push(policyFinding("Cancellation terms do not distinguish standard made to order from bespoke goods."));
  }
  if (!text(policies.privacy, 80)) findings.push(policyFinding("Reviewed privacy content is missing."));
  if (!text(policies.information_officer_name, 3) || !text(policies.information_officer_responsibilities, 40) || !text(policies.paia_baseline, 40)) {
    findings.push(policyFinding("Information Officer and PAIA baseline responsibilities are missing."));
  }
  if (typeof policies.collector_skin !== "string" || !COLLECTOR_SKINS.includes(policies.collector_skin as typeof COLLECTOR_SKINS[number])) {
    findings.push(policyFinding("The final Collector D font and palette is not selected."));
  }
  return findings;
}

function catalogueFindings(value: unknown): LaunchPackFinding[] {
  const catalogue = record(value);
  if (!catalogue) return [ABSENT[1]];
  const findings: LaunchPackFinding[] = [];
  const approved = text(catalogue.approved_by, 3) &&
    typeof catalogue.approved_on === "string" && /^\d{4}-\d{2}-\d{2}$/.test(catalogue.approved_on);
  if (!approved) findings.push(catalogueFinding("The catalogue has no recorded owner approval."));
  const variants = Array.isArray(catalogue.variants) ? catalogue.variants : [];
  if (variants.length < 30 || variants.length > 80) {
    findings.push(catalogueFinding(`Approved sellable variants must number between 30 and 80. This pack has ${variants.length}.`));
  }
  const seenSkus = new Set<string>();
  const seenOptions = new Set<string>();
  variants.forEach((variant, index) => {
    variantProblems(variant, index).forEach((detail) => findings.push(catalogueFinding(detail)));
    const item = record(variant);
    const sku = item && typeof item.sku === "string" ? item.sku.trim() : "";
    if (sku) {
      if (seenSkus.has(sku)) findings.push(catalogueFinding(`SKU ${sku} is used more than once.`));
      seenSkus.add(sku);
    }
    const options = item ? record(item.options) : null;
    const group = item && typeof item.product_group_id === "string" ? item.product_group_id.trim() : "";
    if (options && group) {
      const combination = `${group}:${Object.entries(options).sort(([left], [right]) => left.localeCompare(right)).map(([key, value]) => `${key}: ${String(value)}`).join(", ")}`;
      if (seenOptions.has(combination)) {
        const rendered = combination.slice(group.length + 1);
        findings.push(catalogueFinding(`Group ${group} repeats the ${rendered} combination.`));
      }
      seenOptions.add(combination);
    }
  });
  return findings;
}

export function assessLaunchPack(pack: unknown, now: Date = new Date()): LaunchPackAssessment {
  const root = record(pack);
  if (!root) return { ready: false, findings: ABSENT };
  const hit = { secret: false, customers: false };
  walkPack(root, hit);
  if (hit.secret) return { ready: false, findings: [provisioningFinding("Launch pack must not contain secrets.")] };
  const findings = [
    ...(businessConfirmed(root.business) ? [] : [ABSENT[0]]),
    ...catalogueFindings(root.catalogue),
    ...fulfilmentFindings(root, now),
    ...("policies" in root ? policyFindings(root.policies) : [ABSENT[3]]),
    ...("provisioning" in root ? provisioningFindings(root.provisioning) : [ABSENT[4]]),
    ...(hit.customers ? [provisioningFinding("Customer exports are not part of the launch pack.")] : []),
  ];
  return { ready: findings.length === 0, findings };
}

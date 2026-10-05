import { assessLaunchPack, containsForbiddenSecret } from "./launch-pack";

export type StorefrontCost = {
  storefront_usd_cents: number;
  fits_budget: boolean;
  pending_owner_decision: boolean;
  disclosed_separately_usd_cents: {
    payment_fee: number;
    carrier: number;
    firstout_hosting: number;
  };
};

export type CapacityScore = {
  p95_ms: number | null;
  unexpected_error_rate: number | null;
  meets_profile: boolean;
  hosted: boolean;
};

export const MARROW_RAILWAY_PROJECT_ID = "a633a271-5bb0-461e-8eb5-1acb9e126a59";
export const FIRSTOUT_RAILWAY_PROJECT_ID = "c76d8df1-d839-454c-a94a-79b930deaf38";

export type FirstSaleReadiness = {
  decision: "go" | "no_go";
  public_selling: false;
  public_selling_changed: false;
  release_gate: "open" | "closed";
  post_launch_follow_up: string;
  missing: string[];
  cost: StorefrontCost | null;
  capacity: CapacityScore | null;
};

const ABSENT_MISSING = [
  "Owner catalogue pack is absent.",
  "Reviewed policies are absent.",
  "Provider credentials, callbacks, and sender records are absent.",
  "Named launch operator is absent.",
  "Hosted guest and Clerk purchases were not recorded.",
  "Operator fulfilment, refund, return, and recovery were not recorded.",
  "Consented, rejected, and withdrawn analytics journeys were not recorded.",
  "Private capacity rehearsal was not recorded.",
  "Measured monthly Storefront cost was not recorded.",
  "Environment identity, backups, restore evidence, and alerts were not recorded.",
  "Owner authorization for public selling is absent.",
  "Owner authorization for a real-money rehearsal is absent.",
];

const FOLLOW_UP = "Plan five real orders across at least 14 days after an authorized launch. This is not a prelaunch requirement.";

function record(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function absent(): FirstSaleReadiness {
  return {
    decision: "no_go",
    public_selling: false,
    public_selling_changed: false,
    release_gate: "open",
    post_launch_follow_up: FOLLOW_UP,
    missing: ABSENT_MISSING,
    cost: null,
    capacity: null,
  };
}

const BUDGET_USD_CENTS = 5000;
const STOREFRONT_CATEGORIES = ["compute", "staging", "media", "backups", "saas"] as const;

function cents(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
}

function costAssessment(value: unknown): { problems: string[]; cost: StorefrontCost | null } {
  if (value === undefined) {
    return { problems: ["Measured monthly Storefront cost was not recorded."], cost: null };
  }
  const cost = record(value);
  const assumptions = cost && typeof cost.usage_assumptions === "string" ? cost.usage_assumptions.trim() : "";
  const lines = cost && Array.isArray(cost.lines) ? cost.lines : [];
  if (!cost || cost.measured !== true || assumptions.length < 40 || lines.length === 0) {
    return { problems: ["Measured monthly Storefront cost was not recorded."], cost: null };
  }
  const totals = { storefront: 0, payment_fee: 0, carrier: 0, firstout_hosting: 0 };
  const seen = new Set<string>();
  for (const item of lines) {
    const line = record(item);
    const klass = line?.class;
    const category = line?.category;
    if (!line || !cents(line.usd_cents) || typeof category !== "string" ||
        (klass !== "storefront" && klass !== "payment_fee" && klass !== "carrier" && klass !== "firstout_hosting")) {
      return { problems: ["A Storefront cost line is not a recorded non-negative USD cent amount."], cost: null };
    }
    if (klass === "storefront") {
      if (!STOREFRONT_CATEGORIES.includes(category as typeof STOREFRONT_CATEGORIES[number]) || seen.has(category)) {
        return { problems: ["Storefront cost categories must be compute, staging, media, backups, and SaaS, once each."], cost: null };
      }
      seen.add(category);
      totals.storefront += line.usd_cents;
    } else {
      totals[klass] += line.usd_cents;
    }
  }
  if (STOREFRONT_CATEGORIES.some((category) => !seen.has(category))) {
    return { problems: ["Measured monthly Storefront cost was not recorded."], cost: null };
  }
  const fits = totals.storefront <= BUDGET_USD_CENTS;
  return {
    problems: fits ? [] : ["Measured monthly Storefront cost is above USD 50 and remains a no-go pending an owner decision."],
    cost: {
      storefront_usd_cents: totals.storefront,
      fits_budget: fits,
      pending_owner_decision: !fits,
      disclosed_separately_usd_cents: {
        payment_fee: totals.payment_fee,
        carrier: totals.carrier,
        firstout_hosting: totals.firstout_hosting,
      },
    },
  };
}

function positiveMinor(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0;
}

function joinList(items: string[]): string {
  if (items.length === 1) return items[0];
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

function purchaseFindings(value: unknown): string[] {
  if (!Array.isArray(value)) return ["Hosted guest and Clerk purchases were not recorded."];
  const problems: string[] = [];
  const seen = new Set<string>();
  const covered = new Set<string>();
  value.forEach((item) => {
    const purchase = record(item);
    if (!purchase) {
      problems.push("A purchase record is unreadable.");
      return;
    }
    if (purchase.hosted !== true) problems.push("A purchase was not recorded on the hosted stack.");
    if (purchase.payment !== "verified") {
      problems.push(purchase.commerce_order_id
        ? "An unverified payment produced a commerce order."
        : "A purchase payment was not verified.");
      return;
    }
    const id = typeof purchase.commerce_order_id === "string" ? purchase.commerce_order_id.trim() : "";
    if (!id) problems.push("A verified payment has no commerce order.");
    else if (seen.has(id)) problems.push("A verified payment produced more than one commerce order.");
    else seen.add(id);
    const amount = purchase.amount_minor_zar;
    if (!positiveMinor(amount)) problems.push("A purchase amount is not a positive ZAR minor-unit integer.");
    const firstout = record(purchase.firstout);
    if (!firstout || firstout.sales_order_count !== 1 || firstout.payment_journal_count !== 1) {
      problems.push("A verified payment does not have one Firstout sales order and one payment journal.");
    } else if (firstout.payment_source !== "storefront") {
      problems.push("Firstout recorded the storefront payment as cash or EFT.");
    } else if (firstout.ops_status !== "imported" || firstout.currency !== "ZAR" || firstout.captured_minor_zar !== amount) {
      problems.push("The Firstout financial result does not match the captured ZAR amount.");
    }
    if (purchase.buyer === "guest" || purchase.buyer === "clerk") covered.add(String(purchase.buyer));
    if (purchase.goods === "stocked" || purchase.goods === "confirmed_lead_time") covered.add(String(purchase.goods));
    if (purchase.fulfilment === "gauteng_delivery" || purchase.fulfilment === "collection") covered.add(String(purchase.fulfilment));
  });
  const gaps = [
    ["guest", "a guest"],
    ["clerk", "a Clerk customer"],
    ["stocked", "stocked goods"],
    ["confirmed_lead_time", "confirmed lead-time goods"],
    ["gauteng_delivery", "Gauteng delivery"],
    ["collection", "collection"],
  ].flatMap(([key, label]) => covered.has(key) ? [] : [label]);
  if (gaps.length) problems.push(`Hosted purchases do not yet cover ${joinList(gaps)}.`);
  return problems;
}

function refundProblems(value: unknown, kind: "partial" | "full"): string[] {
  const refund = record(value);
  const label = kind === "partial" ? "partial refund" : "full refund";
  if (!refund || typeof refund.commerce_order_id !== "string" || !refund.commerce_order_id.trim()) {
    return [`The ${label} has no commerce order.`];
  }
  const captured = refund.captured_minor_zar;
  const amount = refund.amount_minor_zar;
  const remaining = refund.remaining_captured_minor_zar;
  if (!positiveMinor(captured) || !positiveMinor(amount) || typeof remaining !== "number" || !Number.isSafeInteger(remaining) || remaining < 0) {
    return [`The ${label} amounts are not ZAR minor units.`];
  }
  if (amount > captured || remaining !== captured - amount) {
    return [`The ${label} exceeds the remaining captured amount.`];
  }
  if (kind === "partial" && (remaining === 0 || amount === captured)) {
    return ["The partial refund clears the whole captured amount."];
  }
  if (kind === "full" && remaining !== 0) {
    return ["The full refund leaves a captured balance."];
  }
  if (refund.restocked !== false) return [`The ${label} put goods back into sellable stock.`];
  return [];
}

function operationFindings(value: unknown): string[] {
  if (value === undefined) return ["Operator fulfilment, refund, return, and recovery were not recorded."];
  const operations = record(value);
  if (!operations) return ["Operator fulfilment evidence is unreadable."];
  const problems: string[] = [];
  if (operations.delivery_progressed !== true) problems.push("Delivery was not progressed.");
  if (operations.collection_progressed !== true) problems.push("Collection was not progressed.");
  problems.push(...refundProblems(operations.partial_refund, "partial"));
  problems.push(...refundProblems(operations.full_refund, "full"));
  const returned = record(operations.separate_return);
  if (!returned || returned.restocked !== true || returned.refund_id !== null ||
      typeof returned.commerce_order_id !== "string" || !returned.commerce_order_id.trim()) {
    problems.push("The return is not separate from the refund.");
  }
  if (operations.customer_status_converged !== true || operations.notifications_converged !== true || operations.reconciliation_converged !== true) {
    problems.push("Customer status, notifications, and reconciliation have not converged.");
  }
  const recovery = record(operations.recovery);
  const closed = recovery ? record(recovery.closed_browser) : null;
  if (!closed || closed.payment_verified !== true || typeof closed.commerce_order_id !== "string" || !closed.commerce_order_id.trim()) {
    problems.push("Closed-browser payment recovery was not recorded.");
  }
  const duplicate = recovery ? record(recovery.duplicate_callback) : null;
  const duplicateIds = duplicate && Array.isArray(duplicate.commerce_order_ids)
    ? duplicate.commerce_order_ids.filter((id) => typeof id === "string" && id.trim())
    : [];
  if (!duplicate || typeof duplicate.attempts !== "number" || duplicate.attempts < 2 || new Set(duplicateIds).size !== 1) {
    problems.push("A duplicate callback created another commerce order.");
  }
  const outage = recovery ? record(recovery.firstout_outage) : null;
  if (!outage || outage.paid_order_retained !== true || outage.handoff_queued !== true) {
    problems.push("A Firstout outage did not retain the paid order.");
  }
  const unknown = recovery ? record(recovery.unknown_outcome) : null;
  if (!unknown || unknown.repeated_financial_action !== false || unknown.reconciled !== true) {
    problems.push("An unknown financial outcome was repeated instead of reconciled.");
  }
  return problems;
}

function nearestRankP95(samples: number[]): number | null {
  if (samples.length === 0) return null;
  const sorted = [...samples].sort((left, right) => left - right);
  const rank = Math.ceil(0.95 * sorted.length);
  return sorted[rank - 1] ?? null;
}

function capacityAssessment(value: unknown): { problems: string[]; capacity: CapacityScore | null } {
  if (value === undefined) {
    return { problems: ["Private capacity rehearsal was not recorded."], capacity: null };
  }
  const run = record(value);
  const samples = run && Array.isArray(run.cart_checkout_samples_ms) ? run.cart_checkout_samples_ms : [];
  const numeric = samples.every((sample) => typeof sample === "number" && Number.isFinite(sample) && sample >= 0);
  const requests = run?.requests;
  const errors = run?.unexpected_errors;
  if (!run || !numeric || samples.length === 0 || typeof requests !== "number" || !Number.isSafeInteger(requests) || requests < 1 ||
      typeof errors !== "number" || !Number.isSafeInteger(errors) || errors < 0 || errors > requests) {
    return { problems: ["Private capacity rehearsal was not recorded."], capacity: null };
  }
  const p95 = nearestRankP95(samples as number[]);
  const rate = errors / requests;
  const hosted = run.source === "hosted_private" && run.private_environment === true && run.simulator_public === false;
  const backlogStart = run.backlog_start;
  const backlogEnd = run.backlog_end;
  const backlogKnown = typeof backlogStart === "number" && typeof backlogEnd === "number";
  const backlogGrew = backlogKnown && backlogEnd > backlogStart;
  const profileShape = run.concurrent_shoppers === 20 &&
    run.duration_minutes === 30 &&
    run.simulator_completions_per_minute === 5 &&
    run.stock_sync_enabled === true;
  const profile = hosted && profileShape && run.oom === false && backlogKnown && !backlogGrew &&
    run.duplicate_effects === 0 && p95 !== null && p95 <= 1000 && rate < 0.01;
  const problems: string[] = [];
  if (run.simulator_public === true) problems.push("The payment simulator is not available on a public deployment.");
  if (!hosted) problems.push("Private capacity rehearsal was not recorded.");
  else if (!profile) {
    if (p95 !== null && p95 > 1000) problems.push("First-party cart and checkout p95 was above 1 second.");
    if (rate >= 0.01) problems.push("Unexpected server errors were not under 1 percent.");
    if (run.oom === true) problems.push("The capacity rehearsal ran out of memory.");
    if (backlogGrew) problems.push("The capacity rehearsal grew a job backlog.");
    if (run.duplicate_effects !== 0) problems.push("The capacity rehearsal duplicated a business effect.");
    if (problems.length === 0) problems.push("The capacity rehearsal did not match the proposed profile.");
  }
  return {
    problems,
    capacity: { p95_ms: p95, unexpected_error_rate: rate, meets_profile: profile, hosted },
  };
}

const PROJECT_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function environmentFindings(value: unknown): string[] {
  if (value === undefined) return ["Environment identity, backups, restore evidence, and alerts were not recorded."];
  const environment = record(value);
  if (!environment) return ["Environment identity evidence is unreadable."];
  const problems: string[] = [];
  const projectId = typeof environment.railway_project_id === "string" ? environment.railway_project_id.trim() : "";
  if (projectId === MARROW_RAILWAY_PROJECT_ID) problems.push("Environment identity points at the Marrow Railway project.");
  else if (projectId === FIRSTOUT_RAILWAY_PROJECT_ID) problems.push("Environment identity points at the Firstout Railway project.");
  else if (!PROJECT_ID.test(projectId) || typeof environment.railway_project_name !== "string" || environment.railway_project_name.trim().length < 3) {
    problems.push("Environment identity was not recorded.");
  }
  if (environment.private_access !== true || environment.indexing_enabled !== false || environment.public_selling_enabled !== false) {
    problems.push("The recorded environment is not a private, non-indexable Storefront with public selling off.");
  }
  const backup = typeof environment.backup_evidence_id === "string" && environment.backup_evidence_id.trim().length > 0;
  const restore = typeof environment.restore_evidence_id === "string" && environment.restore_evidence_id.trim().length > 0;
  const alerts = Array.isArray(environment.alerts)
    ? environment.alerts.filter((alert) => typeof alert === "string" && alert.trim().length > 0)
    : [];
  if (!backup || !restore || alerts.length < 2) problems.push("Backups, restore evidence, or alerts were not recorded.");
  return problems;
}

function providerFindings(value: unknown): string[] {
  if (value === undefined) return ["Provider credentials, callbacks, and sender records are absent."];
  const providers = record(value);
  if (!providers || providers.clerk_callback_recorded !== true || providers.peach_callback_recorded !== true ||
      providers.email_sender_recorded !== true || providers.posthog_eu_recorded !== true) {
    return ["Provider credentials, callbacks, and sender records are absent."];
  }
  return [];
}

const DASHBOARD_IDS = [
  "store_health",
  "acquisition",
  "product_performance",
  "purchase_funnel",
  "search_merchandising",
  "friction_quality",
  "accounts",
];

function analyticsFindings(value: unknown): string[] {
  if (value === undefined) return ["Consented, rejected, and withdrawn analytics journeys were not recorded."];
  const analytics = record(value);
  if (!analytics) return ["Analytics evidence is unreadable."];
  const problems: string[] = [];
  if (analytics.consented !== true || analytics.rejected_stopped !== true || analytics.withdrawn_stopped !== true) {
    problems.push("Consented, rejected, and withdrawn analytics journeys were not recorded.");
  }
  if (analytics.replay_excludes_sensitive_routes !== true) {
    problems.push("Replay exclusions for auth, account, checkout, and confirmation were not recorded.");
  }
  const dashboards = Array.isArray(analytics.dashboards) ? analytics.dashboards.filter((id) => typeof id === "string") : [];
  if (DASHBOARD_IDS.some((id) => !dashboards.includes(id))) problems.push("Analytics dashboards are incomplete.");
  if (analytics.personal_information_exposed !== false) problems.push("Analytics exposed personal information.");
  if (analytics.commerce_blocked !== false) problems.push("Analytics blocked commerce.");
  return problems;
}

function operatorFindings(value: unknown): string[] {
  if (value === undefined) return ["Named launch operator is absent."];
  const operator = record(value);
  const name = operator && typeof operator.name === "string" ? operator.name.trim() : "";
  if (name.length < 3 || name.toLowerCase() === "firstout") return ["Named launch operator is absent."];
  return [];
}

function launchFindings(value: unknown, now: Date): string[] {
  if (value === undefined) {
    return ["Owner catalogue pack is absent.", "Reviewed policies are absent."];
  }
  const assessment = assessLaunchPack(value, now);
  if (assessment.ready) return [];
  return assessment.findings.map((finding) => finding.detail);
}

function ownerDecisionFindings(value: unknown): string[] {
  if (value === undefined) {
    return [
      "Owner authorization for public selling is absent.",
      "Owner authorization for a real-money rehearsal is absent.",
    ];
  }
  const decision = record(value);
  const problems: string[] = [];
  if (!decision || decision.public_selling_authorized !== true) {
    problems.push("Owner authorization for public selling is absent.");
  }
  if (!decision || decision.real_money_rehearsal_authorized !== true) {
    problems.push("Owner authorization for a real-money rehearsal is absent.");
  }
  return problems;
}

function assessmentFrom(root: Record<string, unknown>, now: Date): { missing: string[]; cost: StorefrontCost | null; capacity: CapacityScore | null } {
  const cost = costAssessment("cost" in root ? root.cost : undefined);
  const capacity = capacityAssessment("capacity" in root ? root.capacity : undefined);
  return {
    cost: cost.cost,
    capacity: capacity.capacity,
    missing: [
    ...launchFindings("launch_pack" in root ? root.launch_pack : undefined, now),
    ...providerFindings("providers" in root ? root.providers : undefined),
    ...operatorFindings("operator" in root ? root.operator : undefined),
    ...purchaseFindings("purchases" in root ? root.purchases : undefined),
    ...operationFindings("operations" in root ? root.operations : undefined),
    ...analyticsFindings("analytics" in root ? root.analytics : undefined),
    ...capacity.problems,
    ...cost.problems,
    ...environmentFindings("environment" in root ? root.environment : undefined),
    ...(containsForbiddenSecret(root) ? ["Evidence contains a secret and was not accepted."] : []),
    ...ownerDecisionFindings("owner_decision" in root ? root.owner_decision : undefined),
    ],
  };
}

export type CapacityProbe = {
  refused: boolean;
  reason: "simulator_public" | "publicly_reachable" | null;
  source: "in_process";
  meets_hosted_profile: false;
  duplicate_effects?: number;
  p95_ms?: number | null;
  unexpected_errors?: number;
  requests?: number;
  backlog_grew?: boolean;
  oom?: boolean;
};

/** A short private probe. It never stands in for the 30-minute hosted rehearsal. */
export function runPrivateCapacityProbe(input: {
  publiclyReachable: boolean;
  simulatorPublic: boolean;
  completions: { effectId: string; latencyMs: number; unexpectedError: boolean }[];
  backlogStart?: number;
  backlogEnd?: number;
  oom?: boolean;
}): CapacityProbe {
  if (input.simulatorPublic || input.publiclyReachable) {
    return {
      refused: true,
      reason: input.simulatorPublic ? "simulator_public" : "publicly_reachable",
      source: "in_process",
      meets_hosted_profile: false,
    };
  }
  const seen = new Set<string>();
  let duplicateEffects = 0;
  let unexpectedErrors = 0;
  const samples: number[] = [];
  for (const completion of input.completions) {
    if (seen.has(completion.effectId)) duplicateEffects += 1;
    seen.add(completion.effectId);
    if (completion.unexpectedError) unexpectedErrors += 1;
    samples.push(completion.latencyMs);
  }
  return {
    refused: false,
    reason: null,
    source: "in_process",
    meets_hosted_profile: false,
    duplicate_effects: duplicateEffects,
    p95_ms: nearestRankP95(samples),
    unexpected_errors: unexpectedErrors,
    requests: input.completions.length,
    backlog_grew: (input.backlogEnd ?? 0) > (input.backlogStart ?? 0),
    oom: input.oom === true,
  };
}

/** Recorded evidence only. This function never enables public selling. */
export function assessFirstSaleReadiness(evidence: unknown, now: Date = new Date()): FirstSaleReadiness {
  const root = record(evidence);
  if (!root) return absent();
  const assessed = assessmentFrom(root, now);
  if (assessed.missing.join("\n") === ABSENT_MISSING.join("\n") && assessed.cost === null && assessed.capacity === null) return absent();
  const open = assessed.missing.length > 0;
  return {
    decision: open ? "no_go" : "go",
    public_selling: false,
    public_selling_changed: false,
    release_gate: open ? "open" : "closed",
    post_launch_follow_up: FOLLOW_UP,
    missing: assessed.missing,
    cost: assessed.cost,
    capacity: assessed.capacity,
  };
}

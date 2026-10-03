export const HANDOFF_AGED_THRESHOLD_MS = 5 * 60 * 1000;

export const EXCEPTION_KINDS = [
  "aged_hold",
  "stale_sync",
  "missing_operational_paid_order",
  "unknown_payment",
  "refund_mismatch",
  "fulfilment_drift",
  "capacity_conflict",
] as const;

export type StorefrontExceptionKind = (typeof EXCEPTION_KINDS)[number];
export type QueueClass = "aged" | "terminal" | "retrying";

const SENSITIVE_KEYS = new Set([
  "email",
  "customer_email",
  "phone",
  "card",
  "pan",
  "secret",
  "token",
  "authorization",
  "payment_reference",
  "amount_minor",
]);

export function classifyHandoffQueue(input: {
  status: string;
  createdAtMs: number;
  nowMs: number;
  retryable: boolean;
}): QueueClass {
  if (input.status === "failed" || !input.retryable) {
    return "terminal";
  }
  if (input.nowMs - input.createdAtMs >= HANDOFF_AGED_THRESHOLD_MS || input.status === "aged") {
    return "aged";
  }
  return "retrying";
}

export function redactAlertContext(input: Record<string, unknown>): Record<string, unknown> {
  const context: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(input)) {
    if (SENSITIVE_KEYS.has(key) || /email|secret|token|card/i.test(key)) continue;
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean" || value === null) {
      context[key] = value;
    }
  }
  context.handoff_aged_threshold_seconds = HANDOFF_AGED_THRESHOLD_MS / 1000;
  return context;
}

export function operationalCheckoutBlock(input: {
  checkoutAllowed: boolean;
  lastProjectionAt: string | null;
  nowMs: number;
  maxAgeMs: number;
  opsReachable: boolean;
}): string | null {
  if (!input.opsReachable || !input.checkoutAllowed) {
    return "Checkout is paused because operations are unavailable or the stock projection is stale. Your bag and paid orders are kept for recovery.";
  }
  if (!input.lastProjectionAt) {
    return "Checkout is paused because operations are unavailable or the stock projection is stale. Your bag and paid orders are kept for recovery.";
  }
  const observedMs = Date.parse(input.lastProjectionAt);
  if (!Number.isFinite(observedMs) || input.nowMs - observedMs > input.maxAgeMs) {
    return "Checkout is paused because operations are unavailable or the stock projection is stale. Your bag and paid orders are kept for recovery.";
  }
  return null;
}

export type RepairState = {
  id: string;
  kind: StorefrontExceptionKind;
  status: "open" | "aged" | "terminal" | "resolved";
  providerVerified: boolean;
  effectCount: number;
  lastIdempotencyKey: string | null;
};

export function applyExceptionRepair(
  state: RepairState,
  command: { idempotencyKey: string; providerVerified?: boolean },
): { state: RepairState; outcome: "repaired" | "already_resolved" | "needs_provider" } {
  if ((state.kind === "unknown_payment" || state.kind === "refund_mismatch") && !(command.providerVerified ?? state.providerVerified)) {
    return { state, outcome: "needs_provider" };
  }
  if (state.lastIdempotencyKey === command.idempotencyKey) {
    return { state, outcome: state.status === "resolved" ? "already_resolved" : "repaired" };
  }
  if (state.status === "resolved") {
    return {
      state: { ...state, lastIdempotencyKey: command.idempotencyKey },
      outcome: "already_resolved",
    };
  }
  return {
    state: {
      ...state,
      status: "resolved",
      effectCount: state.effectCount + 1,
      lastIdempotencyKey: command.idempotencyKey,
    },
    outcome: "repaired",
  };
}

type OpsHealth = {
  checkoutAllowed: boolean;
  lastProjectionAt: string | null;
  opsReachable: boolean;
};

const INITIAL_OPS_HEALTH: OpsHealth = {
  checkoutAllowed: false,
  lastProjectionAt: null,
  opsReachable: false,
};

let opsHealth: OpsHealth = { ...INITIAL_OPS_HEALTH };

export function recordOpsCheckoutHealth(next: Partial<OpsHealth>): OpsHealth {
  opsHealth = { ...opsHealth, ...next };
  return opsHealth;
}

export function resetOpsCheckoutHealth(): OpsHealth {
  opsHealth = { ...INITIAL_OPS_HEALTH };
  return opsHealth;
}

export function currentOpsCheckoutHealth(): OpsHealth {
  return opsHealth;
}

export async function refreshOpsCheckoutHealth(now = new Date()): Promise<OpsHealth> {
  const url = process.env.FIRSTOUT_OPS_URL;
  const token = process.env.FIRSTOUT_OPS_TOKEN;
  const companyId = process.env.FIRSTOUT_OPS_COMPANY_ID;
  if (!url || !token || !companyId) {
    return recordOpsCheckoutHealth({ opsReachable: false, checkoutAllowed: false });
  }
  try {
    const response = await fetch(`${url.replace(/\/$/, "")}/checkout-safety`, {
      headers: { Authorization: `Bearer ${token}`, "X-Ops-Company-ID": companyId },
      signal: AbortSignal.timeout(10_000),
    });
    if (!response.ok) {
      return recordOpsCheckoutHealth({ opsReachable: false, checkoutAllowed: false });
    }
    const body = await response.json() as { checkout_allowed?: boolean };
    return recordOpsCheckoutHealth({
      opsReachable: true,
      checkoutAllowed: body.checkout_allowed !== false,
      lastProjectionAt: now.toISOString(),
    });
  } catch {
    return recordOpsCheckoutHealth({ opsReachable: false, checkoutAllowed: false });
  }
}

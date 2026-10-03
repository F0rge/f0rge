import { operationalCheckoutBlock } from "./storefront-commerce-exceptions";

/** Proposed retention. Not an agreed business SLA. No live restore is performed here. */
export const PROPOSED_BACKUP_POLICY = {
  status: "proposal" as const,
  agreed_sla: false as const,
  daily_copies: 14,
  recovery_point_hours: 24,
  restoration_hours_after_operator_start: 4,
};

export const DURABLE_DATASETS = [
  "commerce_postgres",
  "payment_attempts",
  "refund_ledger",
  "order_handoff_outbox",
  "notification_outbox",
  "capacity_reservations",
  "ops_exception_queue",
] as const;

export type DurableDataset = (typeof DURABLE_DATASETS)[number];
export type RecoveryEffect = "payment" | "refund" | "order" | "operational_posting" | "email";
export type RecoveryTruth = "provider" | "order" | "stock" | "capacity";
export type AlertRoute =
  | "stale_stock"
  | "aged_paid_handoff"
  | "webhook_failure"
  | "job_failure"
  | "email_failure"
  | "spending"
  | "backup_missing"
  | "backup_corrupt"
  | "backup_stale";

const EFFECTS: RecoveryEffect[] = ["payment", "refund", "order", "operational_posting", "email"];
const TRUTHS: RecoveryTruth[] = ["provider", "order", "stock", "capacity"];
const BACKUP_ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$/;
const SHA256 = /^[a-f0-9]{64}$/;
const RECOVERY_POINT_MS = PROPOSED_BACKUP_POLICY.recovery_point_hours * 60 * 60 * 1000;
const RESTORATION_MS = PROPOSED_BACKUP_POLICY.restoration_hours_after_operator_start * 60 * 60 * 1000;

export const GATE_TRUTHS =
  "Restored checkout stays gated until provider, order, stock, and capacity are reconciled";
export const FIRSTOUT_DEPENDENCY =
  "Firstout is a required dependency. Checkout stays gated until operations are reachable.";

const QUEUE_CLASS: Record<AlertRoute, "aged" | "terminal" | "retrying"> = {
  stale_stock: "aged",
  aged_paid_handoff: "aged",
  backup_stale: "aged",
  webhook_failure: "retrying",
  job_failure: "retrying",
  email_failure: "retrying",
  spending: "terminal",
  backup_missing: "terminal",
  backup_corrupt: "terminal",
};

export type BackupDataset = { name: string; byteSize: number; sha256: string };

export type BackupManifest = {
  backupId: string;
  capturedAtMs: number;
  credentialsIncluded: boolean;
  datasets: BackupDataset[];
};

export type RecoveryState = {
  restoreId: string;
  laterPayment: boolean;
  laterRefund: boolean;
  truths: Record<RecoveryTruth, "pending" | "reconciled">;
  effects: Record<RecoveryEffect, number>;
  seenKeys: Record<string, string>;
  opsReachable: boolean;
  firstoutDependency: "required";
  liveRestore: false;
  agreedSla: false;
};

export type ReplayOutcome = "applied" | "duplicate" | "needs_provider" | "rejected";
export type ReconcileOutcome = "reconciled" | "already_reconciled" | "needs_provider" | "needs_effect" | "rejected";

function blankEffects(): Record<RecoveryEffect, number> {
  return { payment: 0, refund: 0, order: 0, operational_posting: 0, email: 0 };
}

function blankTruths(): Record<RecoveryTruth, "pending" | "reconciled"> {
  return { provider: "pending", order: "pending", stock: "pending", capacity: "pending" };
}

export function cloneRecovery(state: RecoveryState): RecoveryState {
  return {
    ...state,
    truths: { ...state.truths },
    effects: { ...state.effects },
    seenKeys: { ...state.seenKeys },
  };
}

export function resumeRecovery(state: RecoveryState): RecoveryState {
  return cloneRecovery(state);
}

export function checkoutOf(state: RecoveryState): "gated" | "open" {
  const ready = TRUTHS.every((truth) => state.truths[truth] === "reconciled");
  return ready && state.opsReachable ? "open" : "gated";
}

export function gateReason(state: RecoveryState): string | null {
  if (checkoutOf(state) === "open") return null;
  const ready = TRUTHS.every((truth) => state.truths[truth] === "reconciled");
  if (ready && !state.opsReachable) return FIRSTOUT_DEPENDENCY;
  return GATE_TRUTHS;
}

export function openRestore(input: {
  restoreId: string;
  laterPayment: boolean;
  laterRefund: boolean;
}): RecoveryState {
  if (!input.laterPayment && !input.laterRefund) {
    throw new Error("A later verified payment or refund is required");
  }
  return {
    restoreId: input.restoreId,
    laterPayment: input.laterPayment,
    laterRefund: input.laterRefund,
    truths: blankTruths(),
    effects: blankEffects(),
    seenKeys: {},
    opsReachable: false,
    firstoutDependency: "required",
    liveRestore: false,
    agreedSla: false,
  };
}

export function withOps(state: RecoveryState, opsReachable: boolean): RecoveryState {
  return { ...cloneRecovery(state), opsReachable };
}

export function replayEffect(
  state: RecoveryState,
  event: { effect: RecoveryEffect; idempotencyKey: string; providerVerified?: boolean },
): { state: RecoveryState; outcome: ReplayOutcome } {
  if (!EFFECTS.includes(event.effect)) return { state, outcome: "rejected" };
  if ((event.effect === "payment" || event.effect === "refund") && !event.providerVerified) {
    return { state, outcome: "needs_provider" };
  }
  if (event.effect === "payment" && !state.laterPayment) return { state, outcome: "rejected" };
  if (event.effect === "refund" && !state.laterRefund) return { state, outcome: "rejected" };
  if (state.seenKeys[event.idempotencyKey]) return { state, outcome: "duplicate" };
  const next = cloneRecovery(state);
  if (next.effects[event.effect] >= 1) {
    next.seenKeys[event.idempotencyKey] = event.effect;
    return { state: next, outcome: "duplicate" };
  }
  next.effects[event.effect] = 1;
  next.seenKeys[event.idempotencyKey] = event.effect;
  return { state: next, outcome: "applied" };
}

export function reconcileTruth(
  state: RecoveryState,
  truth: RecoveryTruth,
  providerVerified = false,
): { state: RecoveryState; outcome: ReconcileOutcome } {
  if (state.truths[truth] === "reconciled") return { state, outcome: "already_reconciled" };
  if (truth === "provider") {
    if (!providerVerified) return { state, outcome: "needs_provider" };
    if (!state.laterPayment && !state.laterRefund) return { state, outcome: "rejected" };
    if (state.laterPayment && state.effects.payment !== 1) return { state, outcome: "needs_effect" };
    if (state.laterRefund && state.effects.refund !== 1) return { state, outcome: "needs_effect" };
  } else if (truth === "order") {
    if (state.effects.order !== 1 || state.effects.operational_posting !== 1) {
      return { state, outcome: "needs_effect" };
    }
  } else if (truth !== "stock" && truth !== "capacity") {
    return { state, outcome: "rejected" };
  }
  const next = cloneRecovery(state);
  next.truths[truth] = "reconciled";
  return { state: next, outcome: "reconciled" };
}

export function checkoutAfterRecovery(
  state: RecoveryState,
  ops: {
    checkoutAllowed: boolean;
    lastProjectionAt: string | null;
    nowMs: number;
    maxAgeMs: number;
    opsReachable: boolean;
  },
): { checkout: "gated" | "open"; reason: string | null } {
  if (TRUTHS.some((truth) => state.truths[truth] !== "reconciled")) {
    return { checkout: "gated", reason: GATE_TRUTHS };
  }
  const block = operationalCheckoutBlock(ops);
  if (block || !ops.opsReachable) {
    return { checkout: "gated", reason: block ?? FIRSTOUT_DEPENDENCY };
  }
  return { checkout: "open", reason: null };
}

export function publicBackupId(value: unknown): string {
  return typeof value === "string" && BACKUP_ID.test(value) ? value : "redacted";
}

export function datasetLabel(value: unknown): string {
  return typeof value === "string" && (DURABLE_DATASETS as readonly string[]).includes(value)
    ? value
    : "required durable state";
}

export function routeAlert(route: AlertRoute, input: Record<string, unknown> = {}): {
  route: AlertRoute;
  queueClass: "aged" | "terminal" | "retrying";
  message: string;
  context: Record<string, unknown>;
} {
  const backupId = publicBackupId(input.backup_id);
  const dataset = datasetLabel(input.dataset);
  const showId = backupId !== "redacted";
  const showDataset = dataset !== "required durable state";
  let message: string;
  if (route === "stale_stock") {
    message = "Stock projection is stale. Checkout stays gated until stock truth is reconciled. Refresh the projection and do not decrement stock again.";
  } else if (route === "aged_paid_handoff") {
    message = "Paid handoff is older than five minutes. Replay the existing handoff key and do not create a second order.";
  } else if (route === "webhook_failure") {
    message = "A payment webhook failed. Replay the stored callback only after provider verification and do not capture a second payment.";
  } else if (route === "job_failure") {
    message = "A durable job failed. Restart resumes the same idempotency key and does not post a second operational effect.";
  } else if (route === "email_failure") {
    message = "An order email failed. Replay uses the notification idempotency key and does not send a second message.";
  } else if (route === "spending") {
    message = "A spending signal needs operator review. Checkout stays gated. This alert includes no customer or payment data.";
  } else if (route === "backup_missing") {
    message = `Backup ${showId ? backupId : "redacted"} is missing durable dataset ${dataset}. Checkout stays gated. Take a new protected copy and do not restore this one.`;
  } else if (route === "backup_corrupt") {
    message = `Backup ${showId ? backupId : "redacted"} is corrupt. Checkout stays gated. Do not restore this copy.`;
  } else {
    message = `Backup ${showId ? backupId : "redacted"} is older than the proposed 24-hour recovery point. That point is a proposal, not an agreed SLA. Checkout stays gated.`;
  }
  const context: Record<string, unknown> = {
    route,
    message,
    action: "keep_checkout_gated",
    agreed_sla: false,
    live_restore: false,
  };
  if (showId && (route === "backup_missing" || route === "backup_corrupt" || route === "backup_stale")) {
    context.backup_id = backupId;
  }
  if (showDataset && route === "backup_missing") context.dataset = dataset;
  return { route, queueClass: QUEUE_CLASS[route], message, context };
}

export type BackupAssessment = {
  ok: boolean;
  code: "ok" | "missing" | "corrupt" | "stale";
  message: string | null;
  alert: ReturnType<typeof routeAlert> | null;
};

export function assessBackup(manifest: BackupManifest | null, nowMs: number): BackupAssessment {
  if (!manifest) {
    const alert = routeAlert("backup_missing", {});
    return { ok: false, code: "missing", message: alert.message, alert };
  }
  if (manifest.credentialsIncluded) {
    const alert = routeAlert("backup_corrupt", { backup_id: manifest.backupId });
    return { ok: false, code: "corrupt", message: alert.message, alert };
  }
  const names = manifest.datasets.map((dataset) => dataset.name);
  if (new Set(names).size !== names.length) {
    const alert = routeAlert("backup_corrupt", { backup_id: manifest.backupId });
    return { ok: false, code: "corrupt", message: alert.message, alert };
  }
  for (const required of DURABLE_DATASETS) {
    if (!names.includes(required)) {
      const alert = routeAlert("backup_missing", { backup_id: manifest.backupId, dataset: required });
      return { ok: false, code: "missing", message: alert.message, alert };
    }
  }
  for (const dataset of manifest.datasets) {
    if (!Number.isInteger(dataset.byteSize) || dataset.byteSize <= 0 || !SHA256.test(dataset.sha256)) {
      const alert = routeAlert("backup_corrupt", { backup_id: manifest.backupId });
      return { ok: false, code: "corrupt", message: alert.message, alert };
    }
  }
  if (!Number.isFinite(manifest.capturedAtMs) || manifest.capturedAtMs > nowMs + 5 * 60 * 1000) {
    const alert = routeAlert("backup_corrupt", { backup_id: manifest.backupId });
    return { ok: false, code: "corrupt", message: alert.message, alert };
  }
  if (nowMs - manifest.capturedAtMs > RECOVERY_POINT_MS) {
    const alert = routeAlert("backup_stale", { backup_id: manifest.backupId });
    return { ok: false, code: "stale", message: alert.message, alert };
  }
  return { ok: true, code: "ok", message: null, alert: null };
}

export function validBackup(backupId: string, capturedAtMs: number): BackupManifest {
  return {
    backupId,
    capturedAtMs,
    credentialsIncluded: false,
    datasets: DURABLE_DATASETS.map((name) => ({
      name,
      byteSize: 128,
      sha256: "ab".repeat(32),
    })),
  };
}

export function rehearseRestore(input: {
  backup: BackupManifest | null;
  nowMs: number;
  operatorStartedMs: number;
  operatorFinishedMs: number;
  laterPayment: boolean;
  laterRefund: boolean;
}): {
  live_restore: false;
  agreed_sla: false;
  proposal: typeof PROPOSED_BACKUP_POLICY;
  backup: BackupAssessment;
  recovery: RecoveryState;
  measured: {
    backup_age_ms: number | null;
    rehearsal_elapsed_ms: number;
    within_proposed_recovery_point: boolean;
    within_proposed_restoration: boolean;
  };
} {
  const backup = assessBackup(input.backup, input.nowMs);
  const recovery = openRestore({
    restoreId: "rehearsal",
    laterPayment: input.laterPayment,
    laterRefund: input.laterRefund,
  });
  const age = input.backup ? input.nowMs - input.backup.capturedAtMs : null;
  const elapsed = input.operatorFinishedMs - input.operatorStartedMs;
  return {
    live_restore: false,
    agreed_sla: false,
    proposal: PROPOSED_BACKUP_POLICY,
    backup,
    recovery,
    measured: {
      backup_age_ms: age,
      rehearsal_elapsed_ms: elapsed,
      within_proposed_recovery_point: age !== null && age >= 0 && age <= RECOVERY_POINT_MS,
      within_proposed_restoration: elapsed >= 0 && elapsed <= RESTORATION_MS,
    },
  };
}

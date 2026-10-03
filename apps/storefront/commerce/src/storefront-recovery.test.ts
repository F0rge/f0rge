import { operationalCheckoutBlock } from "./storefront-commerce-exceptions";
import {
  FIRSTOUT_DEPENDENCY,
  GATE_TRUTHS,
  PROPOSED_BACKUP_POLICY,
  assessBackup,
  checkoutAfterRecovery,
  checkoutOf,
  gateReason,
  openRestore,
  reconcileTruth,
  rehearseRestore,
  replayEffect,
  resumeRecovery,
  routeAlert,
  validBackup,
  withOps,
} from "./storefront-recovery";

const NOW = Date.parse("2026-10-03T12:00:00.000Z");
const CAPTURED = Date.parse("2026-10-02T16:00:00.000Z");

test("restore stays gated until provider, order, stock, and capacity are reconciled once", () => {
  const opened = openRestore({ restoreId: "snap-20261002", laterPayment: true, laterRefund: true });
  expect(checkoutOf(opened)).toBe("gated");
  expect(opened.liveRestore).toBe(false);
  expect(opened.agreedSla).toBe(false);
  expect(opened.firstoutDependency).toBe("required");
  expect(gateReason(opened)).toBe(GATE_TRUTHS);
  expect(opened.effects).toEqual({
    payment: 0, refund: 0, order: 0, operational_posting: 0, email: 0,
  });

  expect(replayEffect(opened, { effect: "payment", idempotencyKey: "pay-key-1" }).outcome).toBe("needs_provider");
  const paid = replayEffect(opened, {
    effect: "payment", idempotencyKey: "pay-key-1", providerVerified: true,
  });
  expect(paid.outcome).toBe("applied");
  const resumed = resumeRecovery(paid.state);
  expect(replayEffect(resumed, {
    effect: "payment", idempotencyKey: "pay-key-1", providerVerified: true,
  }).outcome).toBe("duplicate");
  const other = replayEffect(resumed, {
    effect: "payment", idempotencyKey: "pay-key-2", providerVerified: true,
  });
  expect(other.state.effects.payment).toBe(1);

  const refunded = replayEffect(other.state, {
    effect: "refund", idempotencyKey: "refund-key-1", providerVerified: true,
  });
  const ordered = replayEffect(refunded.state, { effect: "order", idempotencyKey: "order-key-1" });
  const posted = replayEffect(ordered.state, {
    effect: "operational_posting", idempotencyKey: "post-key-1",
  });
  const mailed = replayEffect(posted.state, { effect: "email", idempotencyKey: "mail-key-1" });
  expect(mailed.state.effects).toEqual({
    payment: 1, refund: 1, order: 1, operational_posting: 1, email: 1,
  });
  expect(replayEffect(mailed.state, { effect: "email", idempotencyKey: "mail-key-1" }).state.effects.email).toBe(1);
  expect(replayEffect(
    openRestore({ restoreId: "snap-refundless", laterPayment: true, laterRefund: false }),
    { effect: "refund", idempotencyKey: "refund-key-9", providerVerified: true },
  ).outcome).toBe("rejected");

  expect(reconcileTruth(opened, "provider", true).outcome).toBe("needs_effect");
  const stock = reconcileTruth(mailed.state, "stock");
  const capacity = reconcileTruth(stock.state, "capacity");
  expect(capacity.state.effects).toEqual(mailed.state.effects);
  expect(checkoutOf(capacity.state)).toBe("gated");
  expect(reconcileTruth(capacity.state, "provider", false).outcome).toBe("needs_provider");
  const provider = reconcileTruth(capacity.state, "provider", true);
  const order = reconcileTruth(provider.state, "order");
  expect(order.state.truths).toEqual({
    provider: "reconciled", order: "reconciled", stock: "reconciled", capacity: "reconciled",
  });
  expect(checkoutOf(withOps(order.state, false))).toBe("gated");
  expect(gateReason(withOps(order.state, false))).toBe(FIRSTOUT_DEPENDENCY);
  const reopened = withOps(order.state, true);
  expect(checkoutOf(reopened)).toBe("open");
  expect(replayEffect(reopened, { effect: "email", idempotencyKey: "mail-key-2" }).state.effects.email).toBe(1);
  expect(reconcileTruth(reopened, "stock").outcome).toBe("already_reconciled");
});

test("commerce reopening also requires a fresh Firstout health check", () => {
  let state = openRestore({ restoreId: "snap-20261002", laterPayment: true, laterRefund: false });
  state = replayEffect(state, { effect: "payment", idempotencyKey: "pay", providerVerified: true }).state;
  state = replayEffect(state, { effect: "order", idempotencyKey: "order" }).state;
  state = replayEffect(state, { effect: "operational_posting", idempotencyKey: "post" }).state;
  state = reconcileTruth(state, "provider", true).state;
  state = reconcileTruth(state, "order").state;
  state = reconcileTruth(state, "stock").state;
  state = reconcileTruth(state, "capacity").state;
  const down = checkoutAfterRecovery(state, {
    checkoutAllowed: true,
    lastProjectionAt: new Date(NOW).toISOString(),
    nowMs: NOW,
    maxAgeMs: 300_000,
    opsReachable: false,
  });
  expect(down.checkout).toBe("gated");
  expect(down.reason).toMatch(/operations are unavailable|Firstout/);
  const stale = checkoutAfterRecovery(state, {
    checkoutAllowed: true,
    lastProjectionAt: new Date(NOW - 301_000).toISOString(),
    nowMs: NOW,
    maxAgeMs: 300_000,
    opsReachable: true,
  });
  expect(stale.checkout).toBe("gated");
  expect(operationalCheckoutBlock({
    checkoutAllowed: true,
    lastProjectionAt: new Date(NOW).toISOString(),
    nowMs: NOW,
    maxAgeMs: 300_000,
    opsReachable: true,
  })).toBeNull();
  expect(checkoutAfterRecovery(state, {
    checkoutAllowed: true,
    lastProjectionAt: new Date(NOW).toISOString(),
    nowMs: NOW,
    maxAgeMs: 300_000,
    opsReachable: true,
  })).toEqual({ checkout: "open", reason: null });
  const pending = openRestore({ restoreId: "snap-20261002", laterPayment: true, laterRefund: false });
  expect(checkoutAfterRecovery(pending, {
    checkoutAllowed: true,
    lastProjectionAt: new Date(NOW).toISOString(),
    nowMs: NOW,
    maxAgeMs: 300_000,
    opsReachable: true,
  }).reason).toBe(GATE_TRUTHS);
});

test("backup rehearsal records proposed cadence and redacted failure alerts", () => {
  expect(PROPOSED_BACKUP_POLICY).toMatchObject({
    status: "proposal",
    agreed_sla: false,
    daily_copies: 14,
    recovery_point_hours: 24,
    restoration_hours_after_operator_start: 4,
  });
  const rehearsal = rehearseRestore({
    backup: validBackup("rehearsal-20261002", CAPTURED),
    nowMs: NOW,
    operatorStartedMs: NOW,
    operatorFinishedMs: NOW + 12 * 60 * 1000,
    laterPayment: true,
    laterRefund: true,
  });
  expect(rehearsal.live_restore).toBe(false);
  expect(rehearsal.agreed_sla).toBe(false);
  expect(rehearsal.backup.ok).toBe(true);
  expect(rehearsal.recovery.liveRestore).toBe(false);
  expect(checkoutOf(rehearsal.recovery)).toBe("gated");
  expect(rehearsal.measured).toEqual({
    backup_age_ms: 20 * 60 * 60 * 1000,
    rehearsal_elapsed_ms: 12 * 60 * 1000,
    within_proposed_recovery_point: true,
    within_proposed_restoration: true,
  });

  const missing = assessBackup({
    ...validBackup("rehearsal-20261002", CAPTURED),
    datasets: validBackup("rehearsal-20261002", CAPTURED).datasets.filter(
      (dataset) => dataset.name !== "payment_attempts",
    ),
  }, NOW);
  expect(missing.code).toBe("missing");
  expect(missing.alert?.context.dataset).toBe("payment_attempts");
  expect(JSON.stringify(missing.alert?.context)).not.toContain("payer@example.test");

  const corrupt = assessBackup({
    ...validBackup("rehearsal-20261002", CAPTURED),
    credentialsIncluded: true,
  }, NOW);
  expect(corrupt.code).toBe("corrupt");
  const stale = assessBackup(validBackup("rehearsal-20261002", NOW - 25 * 60 * 60 * 1000), NOW);
  expect(stale.code).toBe("stale");
  expect(stale.message).toMatch(/proposal, not an agreed SLA/);

  const spending = routeAlert("spending", {
    customer_email: "payer@example.test",
    amount_minor: 115000,
    token: "secret-token",
  });
  const encoded = JSON.stringify(spending.context);
  expect(encoded).not.toContain("payer@example.test");
  expect(encoded).not.toContain("secret-token");
  expect(encoded).not.toContain("115000");
  expect(routeAlert("webhook_failure").message).toMatch(/do not capture a second payment/);
  expect(routeAlert("job_failure").message).toMatch(/does not post a second operational effect/);
  expect(routeAlert("email_failure").message).toMatch(/does not send a second message/);
  expect(routeAlert("aged_paid_handoff").message).toMatch(/do not create a second order/);
  expect(routeAlert("stale_stock").message).toMatch(/do not decrement stock again/);
});

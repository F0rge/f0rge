import {
  applyExceptionRepair,
  classifyHandoffQueue,
  currentOpsCheckoutHealth,
  HANDOFF_AGED_THRESHOLD_MS,
  operationalCheckoutBlock,
  recordOpsCheckoutHealth,
  redactAlertContext,
  resetOpsCheckoutHealth,
} from "./storefront-commerce-exceptions";

test("classifies aged versus terminal paid-handoff queue items using a five-minute threshold", () => {
  const now = Date.parse("2026-10-03T12:00:00.000Z");
  expect(classifyHandoffQueue({
    status: "retry_wait", createdAtMs: now - HANDOFF_AGED_THRESHOLD_MS, nowMs: now, retryable: true,
  })).toBe("aged");
  expect(classifyHandoffQueue({
    status: "pending", createdAtMs: now - 60_000, nowMs: now, retryable: true,
  })).toBe("retrying");
  expect(classifyHandoffQueue({
    status: "failed", createdAtMs: now - 60_000, nowMs: now, retryable: false,
  })).toBe("terminal");
});

test("redacts customer and payment fields from test-route alert context", () => {
  const context = redactAlertContext({
    kind: "missing_operational_paid_order",
    correlation_id: "storefront:order:seed-missing-handoff",
    customer_email: "payer@example.test",
    payment_reference: "secret-ref",
    amount_minor: 115000,
    last_error: "ops_unavailable",
  });
  expect(context.correlation_id).toBe("storefront:order:seed-missing-handoff");
  expect(context.last_error).toBe("ops_unavailable");
  expect(JSON.stringify(context)).not.toContain("payer@example.test");
  expect(JSON.stringify(context)).not.toContain("secret-ref");
});

test("blocks new checkout on outage or stale projection while stating paid recovery remains", () => {
  const now = Date.parse("2026-10-03T12:00:00.000Z");
  const stale = operationalCheckoutBlock({
    checkoutAllowed: true,
    lastProjectionAt: new Date(now - 301_000).toISOString(),
    nowMs: now,
    maxAgeMs: 300_000,
    opsReachable: true,
  });
  expect(stale).toMatch(/paid orders are kept/);
  const outage = operationalCheckoutBlock({
    checkoutAllowed: true,
    lastProjectionAt: new Date(now).toISOString(),
    nowMs: now,
    maxAgeMs: 300_000,
    opsReachable: false,
  });
  expect(outage).toMatch(/operations are unavailable/);
  expect(operationalCheckoutBlock({
    checkoutAllowed: true,
    lastProjectionAt: new Date(now).toISOString(),
    nowMs: now,
    maxAgeMs: 300_000,
    opsReachable: true,
  })).toBeNull();
});

test("repairs converge without duplicating effects and refuse unverified payment success", () => {
  const missing = {
    id: "ex-missing", kind: "missing_operational_paid_order" as const, status: "aged" as const,
    providerVerified: false, effectCount: 0, lastIdempotencyKey: null,
  };
  const first = applyExceptionRepair(missing, { idempotencyKey: "k1" });
  expect(first.outcome).toBe("repaired");
  expect(first.state.effectCount).toBe(1);
  const replay = applyExceptionRepair(first.state, { idempotencyKey: "k1" });
  expect(replay.state.effectCount).toBe(1);
  const other = applyExceptionRepair(first.state, { idempotencyKey: "k2" });
  expect(other.outcome).toBe("already_resolved");
  expect(other.state.effectCount).toBe(1);

  const unknown = {
    id: "ex-unknown", kind: "unknown_payment" as const, status: "open" as const,
    providerVerified: false, effectCount: 0, lastIdempotencyKey: null,
  };
  expect(applyExceptionRepair(unknown, { idempotencyKey: "pay" }).outcome).toBe("needs_provider");
  expect(applyExceptionRepair(unknown, { idempotencyKey: "pay", providerVerified: true }).state.effectCount).toBe(1);
});

test("records a blocking ops health snapshot for checkout", () => {
  const health = recordOpsCheckoutHealth({ checkoutAllowed: false, opsReachable: false });
  expect(health.checkoutAllowed).toBe(false);
  recordOpsCheckoutHealth({ checkoutAllowed: true, opsReachable: true, lastProjectionAt: "2026-10-03T12:00:00.000Z" });
});

test("starts checkout blocked until ops health is recorded as reachable", () => {
  const health = resetOpsCheckoutHealth();
  expect(health).toEqual({
    checkoutAllowed: false,
    lastProjectionAt: null,
    opsReachable: false,
  });
  expect(currentOpsCheckoutHealth()).toEqual(health);
  const now = Date.parse("2026-10-03T12:00:00.000Z");
  expect(operationalCheckoutBlock({
    ...health,
    nowMs: now,
    maxAgeMs: 300_000,
  })).toMatch(/paid orders are kept/);
  recordOpsCheckoutHealth({
    checkoutAllowed: true,
    opsReachable: true,
    lastProjectionAt: "2026-10-03T12:00:00.000Z",
  });
  expect(operationalCheckoutBlock({
    ...currentOpsCheckoutHealth(),
    nowMs: now,
    maxAgeMs: 300_000,
  })).toBeNull();
});

import type { MedusaContainer } from "@medusajs/framework/types";
import { ContainerRegistrationKeys } from "@medusajs/framework/utils";
import type { Knex } from "knex";
import { updateCartWorkflow } from "@medusajs/medusa/core-flows";
import { withCheckoutInventoryLock } from "./checkout-holds";
import { completePeachWebhook, findPeachAttemptByReference, updatePeachAttempt, type PeachInboxEvent } from "./peach-payment-store";
import { processClaimedPeachWebhook } from "./peach-webhook-processing";

jest.mock("@medusajs/medusa/core-flows", () => ({ processPaymentWorkflow: jest.fn(), updateCartWorkflow: jest.fn() }));
jest.mock("./checkout-holds", () => ({ withCheckoutInventoryLock: jest.fn(), checkoutHoldForCart: jest.fn(), releaseCheckoutHoldWithinLock: jest.fn() }));
jest.mock("./peach-payment-store", () => ({
  ...jest.requireActual("./peach-payment-store"),
  findPeachAttemptByReference: jest.fn(), updatePeachAttempt: jest.fn(), completePeachWebhook: jest.fn(),
}));
jest.mock("./storefront-order-handoff", () => ({ prepareStorefrontOrderHandoff: jest.fn() }));
jest.mock("./storefront-peach-refunds", () => ({ processClaimedPeachRefundWebhook: jest.fn() }));

const event = {
  id: "inbox_paid", lease_token: "lease", event_key: "webhook:paid", webhook_id: "paid",
  payment_type: "DB", merchant_reference: "reference", checkout_id: "checkout", amount_minor: 100000,
  currency_code: "ZAR", result_state: "paid", result_code: "000.100.110", transaction_id: "captured",
  event_timestamp: "2026-10-01T12:00:00.000Z", source: "webhook",
} as PeachInboxEvent;

beforeEach(() => {
  jest.clearAllMocks();
  jest.mocked(withCheckoutInventoryLock).mockImplementation(async (_scope, operation) => operation());
  jest.mocked(findPeachAttemptByReference).mockResolvedValue({
    id: "attempt", payment_session_id: "payses_deleted", merchant_reference: "reference", cart_id: "cart_original",
    checkout_id: "checkout", amount_minor: 100000, currency_code: "ZAR", status: "checkout_created",
    last_event_timestamp: null,
  } as unknown as Awaited<ReturnType<typeof findPeachAttemptByReference>>);
});

test("preserves captured money and recoverable exception after a bag edit deletes the native session", async () => {
  const graph = jest.fn(async ({ entity }: { entity: string }) => ({
    data: entity === "cart" ? [{ id: "cart_original", metadata: { existing: true } }] : [],
  }));
  const cartRun = jest.fn().mockResolvedValue({});
  jest.mocked(updateCartWorkflow).mockReturnValue({ run: cartRun } as unknown as ReturnType<typeof updateCartWorkflow>);
  const container = { resolve: (key: string) => key === ContainerRegistrationKeys.QUERY ? { graph } : undefined } as unknown as MedusaContainer;
  const db = {} as Knex;

  expect(await processClaimedPeachWebhook(container, db, event)).toBe("paid_exception");
  expect(updatePeachAttempt).toHaveBeenCalledWith(db, "attempt", expect.objectContaining({
    status: "captured", captured_transaction_id: "captured", last_event_state: "paid",
  }));
  expect(cartRun).toHaveBeenCalledWith({ input: { id: "cart_original", metadata: expect.objectContaining({
    existing: true, storefront_payment_exception: expect.objectContaining({ session_id: "payses_deleted", status: "paid_exception" }),
  }) } });
  expect(completePeachWebhook).toHaveBeenCalledWith(db, "inbox_paid", "lease", "paid_exception");
});

test("retains an actionable paid inbox even when legacy session and cart binding are unrecoverable", async () => {
  const attempt = await jest.mocked(findPeachAttemptByReference)({} as Knex, "reference");
  jest.mocked(findPeachAttemptByReference).mockResolvedValue({ ...attempt, cart_id: null } as NonNullable<typeof attempt>);
  const db = jest.fn(() => ({ where: () => ({ first: async () => undefined }) })) as unknown as Knex;
  const graph = jest.fn(async () => ({ data: [] }));
  const container = { resolve: () => ({ graph }) } as unknown as MedusaContainer;
  expect(await processClaimedPeachWebhook(container, db, event)).toBe("paid_exception");
  expect(updatePeachAttempt).toHaveBeenCalledWith(db, "attempt", expect.objectContaining({ status: "captured" }));
  expect(completePeachWebhook).toHaveBeenCalledWith(db, "inbox_paid", "lease", "paid_exception");
});

test("does not record a capture for a callback that disagrees with the durable amount", async () => {
  const container = { resolve: jest.fn() } as unknown as MedusaContainer;
  expect(await processClaimedPeachWebhook(container, {} as Knex, { ...event, amount_minor: 100001 })).toBe("ignored");
  expect(updatePeachAttempt).not.toHaveBeenCalled();
});

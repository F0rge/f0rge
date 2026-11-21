import type { MedusaContainer } from "@medusajs/framework/types";
import { ContainerRegistrationKeys } from "@medusajs/framework/utils";
import type { Knex } from "knex";
import { updateCartWorkflow } from "@medusajs/medusa/core-flows";
import { withCheckoutInventoryLock } from "./checkout-holds";
import { completePaystackObservation, findPaystackAttemptByReference, updatePaystackAttempt, type PaystackInboxEvent } from "./paystack-payment-store";
import { processClaimedPaystackObservation } from "./paystack-webhook-processing";

jest.mock("@medusajs/medusa/core-flows", () => ({ processPaymentWorkflow: jest.fn(), updateCartWorkflow: jest.fn() }));
jest.mock("./checkout-holds", () => ({ withCheckoutInventoryLock: jest.fn(), checkoutHoldForCart: jest.fn(), releaseCheckoutHoldWithinLock: jest.fn() }));
jest.mock("./paystack-payment-store", () => ({
  ...jest.requireActual("./paystack-payment-store"),
  findPaystackAttemptByReference: jest.fn(), updatePaystackAttempt: jest.fn(), completePaystackObservation: jest.fn(),
}));
jest.mock("./storefront-order-handoff", () => ({ prepareStorefrontOrderHandoff: jest.fn() }));
jest.mock("./storefront-paystack-refunds", () => ({ processClaimedPaystackRefund: jest.fn() }));

const event = {
  id: "inbox_paid", lease_token: "lease", event_key: "charge:paid", kind: "charge", reference: "dk_reference",
  amount_minor: 100000, currency_code: "ZAR", result_state: "paid", provider_status: "success", transaction_id: "4099260516",
  event_timestamp: "2026-10-01T12:00:00.000Z", source: "webhook",
} as PaystackInboxEvent;

beforeEach(() => {
  jest.clearAllMocks();
  jest.mocked(withCheckoutInventoryLock).mockImplementation(async (_scope, operation) => operation());
  jest.mocked(findPaystackAttemptByReference).mockResolvedValue({
    id: "attempt", payment_session_id: "payses_deleted", reference: "dk_reference", cart_id: "cart_original",
    amount_minor: 100000, currency_code: "ZAR", status: "checkout_created", last_event_timestamp: null,
  } as unknown as Awaited<ReturnType<typeof findPaystackAttemptByReference>>);
});

test("preserves captured money and recoverable exception after a bag edit deletes the native session", async () => {
  const graph = jest.fn(async ({ entity }: { entity: string }) => ({
    data: entity === "cart" ? [{ id: "cart_original", metadata: { existing: true } }] : [],
  }));
  const cartRun = jest.fn().mockResolvedValue({});
  jest.mocked(updateCartWorkflow).mockReturnValue({ run: cartRun } as unknown as ReturnType<typeof updateCartWorkflow>);
  const container = { resolve: (key: string) => key === ContainerRegistrationKeys.QUERY ? { graph } : undefined } as unknown as MedusaContainer;
  const db = {} as Knex;

  expect(await processClaimedPaystackObservation(container, db, event)).toBe("paid_exception");
  expect(updatePaystackAttempt).toHaveBeenCalledWith(db, "attempt", expect.objectContaining({
    status: "captured", transaction_id: "4099260516", last_event_state: "paid",
  }));
  expect(cartRun).toHaveBeenCalledWith({ input: { id: "cart_original", metadata: expect.objectContaining({
    existing: true, storefront_payment_exception: expect.objectContaining({ session_id: "payses_deleted", status: "paid_exception" }),
  }) } });
  expect(completePaystackObservation).toHaveBeenCalledWith(db, "inbox_paid", "lease", "paid_exception");
});

test("retains an actionable paid inbox even when legacy session and cart binding are unrecoverable", async () => {
  const attempt = await jest.mocked(findPaystackAttemptByReference)({} as Knex, "dk_reference");
  jest.mocked(findPaystackAttemptByReference).mockResolvedValue({ ...attempt, cart_id: null } as NonNullable<typeof attempt>);
  const db = jest.fn(() => ({ where: () => ({ first: async () => undefined }) })) as unknown as Knex;
  const graph = jest.fn(async () => ({ data: [] }));
  const container = { resolve: () => ({ graph }) } as unknown as MedusaContainer;
  expect(await processClaimedPaystackObservation(container, db, event)).toBe("paid_exception");
  expect(updatePaystackAttempt).toHaveBeenCalledWith(db, "attempt", expect.objectContaining({ status: "captured" }));
  expect(completePaystackObservation).toHaveBeenCalledWith(db, "inbox_paid", "lease", "paid_exception");
});

test("does not deliver value for a verified charge that disagrees with the durable amount", async () => {
  const container = { resolve: jest.fn() } as unknown as MedusaContainer;
  expect(await processClaimedPaystackObservation(container, {} as Knex, { ...event, amount_minor: 100001 })).toBe("ignored");
  expect(updatePaystackAttempt).not.toHaveBeenCalled();
  // A paid mismatch stays visible to staff instead of being silently ignored.
  expect(completePaystackObservation).toHaveBeenCalledWith({}, "inbox_paid", "lease", "needs_review");
});

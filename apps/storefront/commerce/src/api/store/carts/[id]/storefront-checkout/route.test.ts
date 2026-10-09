import type { MedusaRequest, MedusaResponse } from "@medusajs/framework/http";
import { ContainerRegistrationKeys } from "@medusajs/framework/utils";
import {
  addShippingMethodToCartWorkflow,
  createPaymentCollectionForCartWorkflow,
  createPaymentSessionsWorkflow,
  updateCartWorkflow,
} from "@medusajs/medusa/core-flows";
import { checkoutHoldForCart, withCheckoutInventoryLock } from "../../../../../checkout-holds";
import { POST } from "./route";

jest.mock("@medusajs/medusa/core-flows", () => ({
  addShippingMethodToCartWorkflow: jest.fn(),
  createPaymentCollectionForCartWorkflow: jest.fn(),
  createPaymentSessionsWorkflow: jest.fn(),
  updateCartWorkflow: jest.fn(),
}));
jest.mock("../../../../../checkout-holds", () => ({
  checkoutHoldForCart: jest.fn(),
  withCheckoutInventoryLock: jest.fn(),
}));
jest.mock("../../../../../delivery-zones", () => ({ deliveryZoneForAddress: jest.fn(), deliveryZones: jest.fn(() => []) }));
jest.mock("../../../../../peach-payment-config", () => ({ peachPaymentEnabled: jest.fn(() => false), PEACH_PAYMENT_PROVIDER_ID: "pp_peach_sandbox" }));
jest.mock("../../../../../test-payment-config", () => ({ testPaymentEnabled: jest.fn(() => true) }));

function fixture(customerId: string | null) {
  const cart = {
    id: "cart_checkout_test",
    email: "guest@example.test",
    customer_id: customerId,
    total: 1234,
    currency_code: "zar",
    metadata: {
      storefront_claimable_version: "stale",
      storefront_owner_claim: { previous: "must be removed" },
      storefront_order_snapshot: { financial: { total: 1234 }, contact: { email: "guest@example.test" } },
      immutable_handoff_snapshot: { payload: "keep" },
    },
  };
  const graph = jest.fn(async ({ entity }: { entity: string }) => {
    if (entity === "order_cart") return { data: [] };
    if (entity === "cart") return { data: [cart] };
    if (entity === "cart_payment_collection") return { data: [] };
    if (entity === "shipping_option") return { data: [{ id: "so_collection", name: "Collection" }] };
    throw new Error(`Unexpected query entity: ${entity}`);
  });
  const req = {
    params: { id: cart.id },
    body: {
      email: "guest@example.test",
      first_name: "Guest",
      last_name: "Buyer",
      phone: "+27123456789",
      fulfillment_type: "collection",
      confirmation_token: "x".repeat(43),
    },
    scope: { resolve: (key: string) => key === ContainerRegistrationKeys.QUERY ? { graph } : undefined },
  } as unknown as MedusaRequest;
  const response = {
    headers: {} as Record<string, string>,
    statusCode: 0,
    body: undefined as unknown,
    setHeader(name: string, value: string) { this.headers[name] = value; return this; },
    status(code: number) { this.statusCode = code; return this; },
    json(body: unknown) { this.body = body; return this; },
  } as unknown as MedusaResponse & { statusCode: number; body: unknown; headers: Record<string, string> };
  return { req, response, cart };
}

async function runCheckout(customerId: string | null) {
  const updateCartRun = jest.fn(async (_input: { input: { id: string; metadata: Record<string, unknown> } }) => ({}));
  const collectionRun = jest.fn(async () => ({ result: { id: "paycol_test" } }));
  const paymentSessionRun = jest.fn(async () => ({ result: {
    id: "payses_test", status: "pending", amount: 1234, currency_code: "zar", provider_id: "pp_storefront-test_local", data: {},
  } }));
  const shippingRun = jest.fn(async () => ({}));
  (updateCartWorkflow as unknown as jest.Mock).mockReturnValue({ run: updateCartRun });
  (createPaymentCollectionForCartWorkflow as unknown as jest.Mock).mockReturnValue({ run: collectionRun });
  (createPaymentSessionsWorkflow as unknown as jest.Mock).mockReturnValue({ run: paymentSessionRun });
  (addShippingMethodToCartWorkflow as unknown as jest.Mock).mockReturnValue({ run: shippingRun });
  (checkoutHoldForCart as unknown as jest.Mock).mockResolvedValue({ ready: true, expires_at: "2026-10-01T12:00:00.000Z" });
  (withCheckoutInventoryLock as unknown as jest.Mock).mockImplementation(async (_scope: unknown, operation: () => Promise<unknown>) => operation());
  const state = fixture(customerId);
  await POST(state.req, state.response);
  return { ...state, updateCartRun, paymentSessionRun };
}

beforeEach(() => jest.clearAllMocks());

test("marks a newly created guest checkout claimable while preserving immutable order snapshots", async () => {
  const { response, updateCartRun, paymentSessionRun } = await runCheckout(null);
  expect(response.statusCode).toBe(200);
  expect(paymentSessionRun).toHaveBeenCalledTimes(1);
  const metadata = updateCartRun.mock.calls[0]?.[0]?.input.metadata;
  if (!metadata) throw new Error("Checkout did not persist metadata");
  expect(metadata.storefront_claimable_version).toBe(1);
  expect(metadata).not.toHaveProperty("storefront_owner_claim");
  expect(metadata.storefront_order_snapshot).toEqual({ financial: { total: 1234 }, contact: { email: "guest@example.test" } });
  expect(metadata.immutable_handoff_snapshot).toEqual({ payload: "keep" });
  expect(metadata).toHaveProperty("storefront_confirmation_sha256");
});

test("never leaves the guest claim marker on a checkout already owned by a customer", async () => {
  const { response, updateCartRun } = await runCheckout("cus_owned");
  expect(response.statusCode).toBe(200);
  const metadata = updateCartRun.mock.calls[0]?.[0]?.input.metadata;
  if (!metadata) throw new Error("Checkout did not persist metadata");
  expect(metadata).not.toHaveProperty("storefront_claimable_version");
  expect(metadata).not.toHaveProperty("storefront_owner_claim");
  expect(metadata.storefront_order_snapshot).toEqual({ financial: { total: 1234 }, contact: { email: "guest@example.test" } });
});

test("binds the durable payment to the original cart and immutable checkout snapshot before provider initiation", async () => {
  const { response, cart, paymentSessionRun } = await runCheckout(null);
  expect(response.statusCode).toBe(200);
  expect(paymentSessionRun).toHaveBeenCalledWith({ input: expect.objectContaining({
    data: { storefront_cart_id: cart.id, storefront_checkout_snapshot: cart },
  }) });
});

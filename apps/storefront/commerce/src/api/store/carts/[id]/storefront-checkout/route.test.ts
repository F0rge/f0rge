import type { MedusaRequest, MedusaResponse } from "@medusajs/framework/http";
import { ContainerRegistrationKeys, Modules } from "@medusajs/framework/utils";
import {
  addShippingMethodToCartWorkflow,
  createPaymentCollectionForCartWorkflow,
  createPaymentSessionsWorkflow,
  updateCartWorkflow,
} from "@medusajs/medusa/core-flows";
import { checkoutHoldForCart, withCheckoutInventoryLock } from "../../../../../checkout-holds";
import { deliveryZoneForAddress } from "../../../../../delivery-zones";
import { clearCheckoutShippingWorkflow } from "../../../../../storefront-checkout-shipping";
import { testPaymentEnabled } from "../../../../../test-payment-config";
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
jest.mock("../../../../../storefront-checkout-shipping", () => ({ clearCheckoutShippingWorkflow: jest.fn() }));
jest.mock("../../../../../paystack-payment-config", () => ({ paystackPaymentEnabled: jest.fn(() => false), PAYSTACK_PAYMENT_PROVIDER_ID: "pp_paystack_checkout" }));
jest.mock("../../../../../test-payment-config", () => ({ testPaymentEnabled: jest.fn(() => true) }));

type CheckoutBody = Record<string, unknown>;
type ShippingMethod = { id: string; shipping_option_id: string };

function fixture(customerId: string | null) {
  const cart = {
    id: "cart_checkout_test",
    email: "guest@example.test",
    customer_id: customerId,
    total: 1234,
    shipping_total: 0,
    items: [{ id: "line_1", title: "Test Chair", variant_id: "variant_1", quantity: 1, unit_price: 1234, total: 1234 }],
    shipping_methods: [] as ShippingMethod[],
    currency_code: "zar",
    metadata: {
      storefront_claimable_version: "stale",
      storefront_owner_claim: { previous: "must be removed" },
      storefront_order_snapshot: { financial: { total: 1234 }, contact: { email: "guest@example.test" } },
      immutable_handoff_snapshot: { payload: "keep" },
    } as Record<string, unknown>,
  };
  const state = {
    deliveryAmount: 1100,
    paymentCollectionAmount: undefined as number | undefined,
    existingSession: undefined as Record<string, unknown> | undefined,
  };
  const graph = jest.fn(async ({ entity, filters }: { entity: string; filters?: Record<string, unknown> }) => {
    if (entity === "order_cart") return { data: [] };
    if (entity === "cart") return { data: [cart] };
    if (entity === "cart_payment_collection") return { data: state.existingSession ? [{ payment_collection_id: "paycol_test" }] : [] };
    if (entity === "payment_collection") return { data: [{ amount: state.paymentCollectionAmount ?? cart.total, currency_code: cart.currency_code }] };
    if (entity === "payment_session") return { data: state.existingSession ? [state.existingSession] : [] };
    if (entity === "shipping_option") return { data: [{ id: filters?.name === "Collection" ? "so_collection" : "so_delivery", name: filters?.name }] };
    throw new Error("Unexpected query entity: " + entity);
  });
  const updateNativeCart = jest.fn(async (_id: string, input: Record<string, unknown>) => Object.assign(cart, input));
  const req = {
    params: { id: cart.id },
    body: {
      email: "guest@example.test",
      first_name: "Guest",
      last_name: "Buyer",
      phone: "+27123456789",
      fulfillment_type: "collection",
      confirmation_token: "x".repeat(43),
    } as CheckoutBody,
    scope: { resolve: (key: string) => key === ContainerRegistrationKeys.QUERY ? { graph }
      : key === Modules.LOCKING ? { execute: async (_key: string, operation: () => Promise<unknown>) => operation() }
      : key === Modules.CART ? { retrieveCart: async () => cart, updateCarts: updateNativeCart } : undefined },
  };
  async function send(body: CheckoutBody = {}) {
    const responseData = {
      headers: {} as Record<string, string>,
      statusCode: 0,
      body: undefined as unknown,
      setHeader(name: string, value: string) { this.headers[name] = value; return this; },
      status(code: number) { this.statusCode = code; return this; },
      json(body: unknown) { this.body = body; return this; },
    };
    await POST({ ...req, body: { ...req.body, ...body } } as unknown as MedusaRequest, responseData as unknown as MedusaResponse);
    return responseData;
  }

  const updateCartRun = jest.fn(async (_input: { input: { id: string; shipping_address: Record<string, unknown> } }) => ({}));
  const clearShippingRun = jest.fn(async () => { cart.shipping_methods = []; });
  const collectionRun = jest.fn(async () => ({ result: { id: "paycol_test" } }));
  const paymentSessionRun = jest.fn(async () => {
    state.existingSession = { id: "payses_test", status: "pending", amount: cart.total, currency_code: "zar", provider_id: "pp_storefront-test_local", data: {} };
    return { result: state.existingSession };
  });
  const shippingRun = jest.fn(async ({ input }: { input: { options: { id: string }[] } }) => {
    const option = input.options[0]?.id;
    cart.shipping_total = option === "so_delivery" ? state.deliveryAmount : 0;
    cart.shipping_methods = [{ id: "method_" + shippingRun.mock.calls.length, shipping_option_id: option ?? "" }];
    cart.total = cart.items.reduce((total, item) => total + item.total, 0) + cart.shipping_total;
    return {};
  });
  (updateCartWorkflow as unknown as jest.Mock).mockReturnValue({ run: updateCartRun });
  (clearCheckoutShippingWorkflow as unknown as jest.Mock).mockReturnValue({ run: clearShippingRun });
  (createPaymentCollectionForCartWorkflow as unknown as jest.Mock).mockReturnValue({ run: collectionRun });
  (createPaymentSessionsWorkflow as unknown as jest.Mock).mockReturnValue({ run: paymentSessionRun });
  (addShippingMethodToCartWorkflow as unknown as jest.Mock).mockReturnValue({ run: shippingRun });
  (checkoutHoldForCart as unknown as jest.Mock).mockResolvedValue({
    ready: true,
    expires_at: "2026-10-01T12:00:00.000Z",
    fulfillment_promise: { version: 1, kind: "stocked", accepted_at: "2026-10-01T11:50:00.000Z", estimated_from: "2026-10-01", estimated_by: "2026-10-31" },
  });
  (withCheckoutInventoryLock as unknown as jest.Mock).mockImplementation(async (_scope: unknown, operation: () => Promise<unknown>) => operation());
  return { send, cart, state, updateCartRun, clearShippingRun, updateNativeCart, collectionRun, paymentSessionRun };
}

function reviewedQuote(body: unknown) {
  if (!body || typeof body !== "object" || !("quote" in body) || !body.quote || typeof body.quote !== "object" ||
      !("review_token" in body.quote) || typeof body.quote.review_token !== "string") {
    throw new Error("Checkout did not return a review token");
  }
  return body.quote as { amount: number; delivery_amount: number; review_token: string };
}

async function runCheckout(customerId: string | null) {
  const checkout = fixture(customerId);
  const review = await checkout.send({ step: "review" });
  expect(review.statusCode).toBe(200);
  const quote = reviewedQuote(review.body);
  const response = await checkout.send({ step: "payment", review_token: quote.review_token });
  return { ...checkout, quote, response };
}

const secret = process.env.STOREFRONT_BFF_SECRET;
beforeAll(() => { process.env.STOREFRONT_BFF_SECRET = "test-storefront-bff-secret-at-least-32-characters"; });
afterAll(() => {
  if (secret === undefined) delete process.env.STOREFRONT_BFF_SECRET;
  else process.env.STOREFRONT_BFF_SECRET = secret;
});
beforeEach(() => jest.clearAllMocks());

test("reviews a free Wynberg collection without creating any payment or order confirmation capability", async () => {
  const { send, cart, updateCartRun, updateNativeCart, collectionRun, paymentSessionRun } = fixture(null);
  const response = await send({ step: "review", confirmation_token: undefined });
  expect(response.statusCode).toBe(200);
  expect(response.headers).toHaveProperty("Cache-Control", "private, no-store, max-age=0");
  expect(response.body).toEqual({ quote: {
    amount: 1234, currency_code: "zar", delivery_amount: 0,
    hold_expires_at: "2026-10-01T12:00:00.000Z",
    fulfillment_promise: { version: 1, kind: "stocked", accepted_at: "2026-10-01T11:50:00.000Z", estimated_from: "2026-10-01", estimated_by: "2026-10-31" },
    items: [{ id: "line_1", title: "Test Chair", quantity: 1, total: 1234 }],
    review_token: expect.stringMatching(/^[a-f0-9]{64}$/),
  } });
  expect(updateCartRun).toHaveBeenCalledWith({ input: {
    id: cart.id, shipping_address: expect.objectContaining({
      address_1: "32 4th Street", address_2: "Wynberg", city: "Sandton", province: "Gauteng", postal_code: "2090", country_code: "za",
    }),
  } });
  expect(cart.metadata).not.toHaveProperty("storefront_confirmation_sha256");
  expect(updateNativeCart).not.toHaveBeenCalled();
  expect(collectionRun).not.toHaveBeenCalled();
  expect(paymentSessionRun).not.toHaveBeenCalled();
});

test("marks a newly created guest checkout claimable while preserving immutable order snapshots", async () => {
  const { response, cart, paymentSessionRun } = await runCheckout(null);
  expect(response.statusCode).toBe(200);
  expect(paymentSessionRun).toHaveBeenCalledTimes(1);
  expect(cart.metadata.storefront_claimable_version).toBe(1);
  expect(cart.metadata).not.toHaveProperty("storefront_owner_claim");
  expect(cart.metadata.storefront_order_snapshot).toEqual({ financial: { total: 1234 }, contact: { email: "guest@example.test" } });
  expect(cart.metadata.immutable_handoff_snapshot).toEqual({ payload: "keep" });
  expect(cart.metadata).toHaveProperty("storefront_confirmation_sha256");
});

test("never leaves the guest claim marker on a checkout already owned by a customer", async () => {
  const { response, cart } = await runCheckout("cus_owned");
  expect(response.statusCode).toBe(200);
  expect(cart.metadata).not.toHaveProperty("storefront_claimable_version");
  expect(cart.metadata).not.toHaveProperty("storefront_owner_claim");
  expect(cart.metadata.storefront_order_snapshot).toEqual({ financial: { total: 1234 }, contact: { email: "guest@example.test" } });
});

test("binds payment to the original cart, immutable checkout snapshot and required email, and safely retries an existing session", async () => {
  const { send, response, quote, cart, updateCartRun, paymentSessionRun } = await runCheckout(null);
  expect(response.statusCode).toBe(200);
  expect(paymentSessionRun).toHaveBeenCalledWith({ input: expect.objectContaining({
    data: { storefront_cart_id: cart.id, storefront_checkout_snapshot: cart, storefront_customer_email: "guest@example.test" },
  }) });
  const retryReview = await send({ step: "review" });
  expect(reviewedQuote(retryReview.body)).toEqual(quote);
  const retry = await send({ step: "payment", review_token: quote.review_token });
  expect(retry.statusCode).toBe(200);
  expect(retry.body).toEqual(response.body);
  expect(updateCartRun).toHaveBeenCalledTimes(2);
  expect(paymentSessionRun).toHaveBeenCalledTimes(1);
});

test("resumes the accepted quote with the current hold expiry after renewal", async () => {
  const { send, quote, paymentSessionRun } = await runCheckout(null);
  const renewedExpiry = "2026-10-01T12:15:00.000Z";
  (checkoutHoldForCart as unknown as jest.Mock).mockResolvedValue({ ready: true, expires_at: renewedExpiry });
  const review = await send({ step: "review" });
  expect(review.statusCode).toBe(200);
  expect(review.body).toEqual({ quote: { ...quote, hold_expires_at: renewedExpiry } });
  const payment = await send({ step: "payment", review_token: quote.review_token });
  expect(payment.statusCode).toBe(200);
  expect(payment.body).toMatchObject({ checkout: { hold_expires_at: renewedExpiry } });
  expect(paymentSessionRun).toHaveBeenCalledTimes(1);
});

test("rejects a new payment without a review, including from a pre-release client", async () => {
  const { send, updateCartRun, collectionRun, paymentSessionRun } = fixture(null);
  for (const body of [{}, { step: "payment" }]) {
    const response = await send(body);
    expect(response.statusCode).toBe(409);
    expect(response.body).toMatchObject({ code: "checkout_review_changed" });
  }
  expect(updateCartRun).not.toHaveBeenCalled();
  expect(collectionRun).not.toHaveBeenCalled();
  expect(paymentSessionRun).not.toHaveBeenCalled();
});

test("invalidates a reviewed delivery when the server rate or the customer details change", async () => {
  (deliveryZoneForAddress as jest.Mock).mockReturnValue({ id: "johannesburg" });
  const { send, state, clearShippingRun, collectionRun, paymentSessionRun } = fixture(null);
  const delivery = {
    fulfillment_type: "delivery", address_1: "10 Example Road", address_2: "Rosebank",
    city: "Johannesburg", province: "Gauteng", postal_code: "2196",
  };
  const review = await send({ ...delivery, step: "review" });
  expect(review.statusCode).toBe(200);
  expect(review.body).toMatchObject({ quote: { amount: 2334, currency_code: "zar", delivery_amount: 1100 } });
  const quote = reviewedQuote(review.body);
  const detailsChanged = await send({ ...delivery, address_1: "20 Example Road", step: "payment", review_token: quote.review_token });
  expect(detailsChanged.statusCode).toBe(409);
  state.deliveryAmount = 1300;
  const rateChanged = await send({ ...delivery, step: "payment", review_token: quote.review_token });
  expect(rateChanged.statusCode).toBe(409);
  expect(rateChanged.body).toMatchObject({ code: "checkout_review_changed" });
  expect(collectionRun).not.toHaveBeenCalled();
  expect(paymentSessionRun).not.toHaveBeenCalled();

  const collectionReview = await send({ step: "review" });
  expect(collectionReview.statusCode).toBe(200);
  expect(collectionReview.body).toMatchObject({ quote: { amount: 1234, delivery_amount: 0 } });
  expect(clearShippingRun).toHaveBeenCalledWith({ input: { shipping_method_ids: ["method_2"] } });
});

test("requires the latest review after switching from collection to delivery", async () => {
  (deliveryZoneForAddress as jest.Mock).mockReturnValue({ id: "pretoria" });
  const { send, state, updateCartRun, collectionRun, paymentSessionRun } = fixture(null);
  const collection = reviewedQuote((await send({ step: "review" })).body);
  state.deliveryAmount = 1300;
  const delivery = {
    fulfillment_type: "delivery", address_1: "10 Example Road", address_2: "Hatfield",
    city: "Pretoria", province: "Gauteng", postal_code: "0083",
  };
  const review = await send({ ...delivery, step: "review" });
  expect(review.body).toMatchObject({ quote: { amount: 2534, delivery_amount: 1300 } });
  const stale = await send({ step: "payment", review_token: collection.review_token });
  expect(stale.statusCode).toBe(409);
  expect(stale.body).toMatchObject({ code: "checkout_review_changed" });
  expect(updateCartRun).toHaveBeenCalledTimes(2);
  expect(collectionRun).not.toHaveBeenCalled();
  expect(paymentSessionRun).not.toHaveBeenCalled();
  const accepted = await send({ ...delivery, step: "payment", review_token: reviewedQuote(review.body).review_token });
  expect(accepted.statusCode).toBe(200);
  expect(paymentSessionRun).toHaveBeenCalledTimes(1);
});

test("rejects a payment collection whose amount differs from the accepted quote", async () => {
  const { send, state, paymentSessionRun } = fixture(null);
  const review = await send({ step: "review" });
  const quote = reviewedQuote(review.body);
  state.paymentCollectionAmount = 100;
  const response = await send({ step: "payment", review_token: quote.review_token });
  expect(response.statusCode).toBe(409);
  expect(response.body).toMatchObject({ code: "checkout_review_changed" });
  expect(paymentSessionRun).not.toHaveBeenCalled();
});

test("answers a stable payment_unavailable code before touching the bag when no card provider is configured", async () => {
  (testPaymentEnabled as jest.Mock).mockReturnValueOnce(false);
  const response = await fixture(null).send({ step: "review" });
  expect(response.statusCode).toBe(404);
  expect(response.body).toEqual({ code: "payment_unavailable", message: "Checkout is not available here" });
  expect(withCheckoutInventoryLock).not.toHaveBeenCalled();
});

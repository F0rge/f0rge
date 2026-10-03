import {
  PEACH_REFUND_URL, peachCheckoutSignature, peachRefundPayment, parsePeachRefundResponse, peachRefundOutcome,
} from "./peach-refunds";
import type { PeachPaymentConfig } from "./peach-payment-config";
import { confirmsRefundDispatchingBarrier, confirmsRefundDispatchingResponse } from "./storefront-peach-refunds";
import type { PeachRefundCommand } from "./peach-payment-store";

const captureId = "8ac7a4a284c684140184c7a8f19a5530";
const refundId = "8ac7a49f8af08e94018af09246760e30";
const secret = "test-checkout-signing-secret";
const dispatchCommand: PeachRefundCommand = {
  request_id: "refund-request-1",
  handoff_id: "handoff-1",
  external_order_id: "order-1",
  original_transaction_id: captureId,
  amount_minor: 500,
  currency_code: "ZAR",
  cancel_order: false,
  allocation: {},
  status: "requested",
};

test("only an exact durable dispatching acknowledgement crosses the Peach POST barrier", () => {
  expect(confirmsRefundDispatchingBarrier({
    id: dispatchCommand.request_id,
    amount_minor: dispatchCommand.amount_minor,
    currency_code: dispatchCommand.currency_code,
    status: "dispatching",
  }, dispatchCommand)).toBe(true);

  // Firstout returns 2xx for already-terminal rows too; those are not new
  // dispatch authorization and must never result in another provider POST.
  for (const status of ["requested", "unknown", "pending", "succeeded", "failed", "needs_review"]) {
    expect(confirmsRefundDispatchingBarrier({
      id: dispatchCommand.request_id,
      amount_minor: dispatchCommand.amount_minor,
      currency_code: dispatchCommand.currency_code,
      status,
    }, dispatchCommand)).toBe(false);
  }
  expect(confirmsRefundDispatchingBarrier({
    id: "different-request",
    amount_minor: dispatchCommand.amount_minor,
    currency_code: dispatchCommand.currency_code,
    status: "dispatching",
  }, dispatchCommand)).toBe(false);
  expect(confirmsRefundDispatchingBarrier({
    id: dispatchCommand.request_id,
    amount_minor: dispatchCommand.amount_minor + 1,
    currency_code: dispatchCommand.currency_code,
    status: "dispatching",
  }, dispatchCommand)).toBe(false);
  expect(confirmsRefundDispatchingBarrier({
    id: dispatchCommand.request_id,
    amount_minor: dispatchCommand.amount_minor,
    currency_code: "USD",
    status: "dispatching",
  }, dispatchCommand)).toBe(false);
  expect(confirmsRefundDispatchingBarrier(null, dispatchCommand)).toBe(false);
  expect(confirmsRefundDispatchingBarrier({ malformed: true }, dispatchCommand)).toBe(false);
});

test("2xx dispatch outcome must contain parseable matching dispatching facts", async () => {
  const response = (body: string, status = 200) => new Response(body, { status });
  expect(await confirmsRefundDispatchingResponse(response(JSON.stringify({
    id: dispatchCommand.request_id,
    amount_minor: dispatchCommand.amount_minor,
    currency_code: dispatchCommand.currency_code,
    status: "dispatching",
  })), dispatchCommand)).toBe(true);
  expect(await confirmsRefundDispatchingResponse(response(JSON.stringify({
    id: dispatchCommand.request_id,
    amount_minor: dispatchCommand.amount_minor,
    currency_code: dispatchCommand.currency_code,
    status: "succeeded",
  })), dispatchCommand)).toBe(false);
  expect(await confirmsRefundDispatchingResponse(response("not-json"), dispatchCommand)).toBe(false);
  expect(await confirmsRefundDispatchingResponse(response("{}"), dispatchCommand)).toBe(false);
  expect(await confirmsRefundDispatchingResponse(response("{}", 503), dispatchCommand)).toBe(false);
});

function signedResponse(resultCode: string, overrides: Record<string, unknown> = {}) {
  const body: Record<string, unknown> = {
    id: refundId,
    paymentType: "RF",
    amount: "5.00",
    currency: "ZAR",
    timestamp: "2026-10-01T12:30:00.000Z",
    result: { code: resultCode, description: "provider result" },
    ...overrides,
  };
  const signature = peachCheckoutSignature({
    amount: String(body.amount),
    currency: String(body.currency),
    id: String(body.id),
    paymentType: String(body.paymentType),
    "result.code": resultCode,
    "result.description": "provider result",
    timestamp: String(body.timestamp),
    ...(typeof body.referencedId === "string" ? { referencedId: body.referencedId } : {}),
  }, secret);
  return { ...body, signature };
}

test("Checkout signature canonicalization matches Peach's documented sorted parameter string", () => {
  const params = {
    amount: "2",
    "authentication.entityId": "8ac7a4ca68c22c4d0168c2caab2e0025",
    currency: "ZAR",
    defaultPaymentMethod: "CARD",
    merchantTransactionId: "Test1234",
    nonce: "JHGJSGHDSKJHGJDHGJH",
    paymentType: "DB",
    shopperResultUrl: "https://example.com/example-webhook",
  };
  const canonical = Object.keys(params).sort().map((key) => `${key}${params[key as keyof typeof params]}`).join("");
  expect(canonical).toBe("amount2authentication.entityId8ac7a4ca68c22c4d0168c2caab2e0025currencyZARdefaultPaymentMethodCARDmerchantTransactionIdTest1234nonceJHGJSGHDSKJHGJDHGJHpaymentTypeDBshopperResultUrlhttps://example.com/example-webhook");
  // Independent SHA-256 HMAC vector for the exact canonical string above.
  expect(peachCheckoutSignature(params, "3fcd7cf22f55119eadbe02d14de18c0c"))
    .toBe("fc1273384a7806c00a6e0512e902be4ed2181af8b72030653310dfc385d1eab4");
});

test("uses standard HMAC-SHA256 bytes for the RFC 4231 known vector", () => {
  expect(peachCheckoutSignature({ "": "what do ya want for nothing?" }, "Jefe"))
    .toBe("5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843");
});

test("verifies a signed successful refund even when the response omits the capture reference", () => {
  const observation = parsePeachRefundResponse(signedResponse("000.100.110"), secret, {
    referencedCaptureId: captureId,
    amountMinor: 500,
    currencyCode: "ZAR",
  });
  expect(observation).toMatchObject({
    provider_refund_id: refundId,
    referenced_capture_id: captureId,
    amount_minor: 500,
    currency_code: "ZAR",
    result_code: "000.100.110",
    outcome: "succeeded",
  });
});

test("posts a classic Checkout refund using its HMAC secret without requesting a V2 OAuth token", async () => {
  const config: PeachPaymentConfig = {
    clientId: "v2-client-id",
    clientSecret: "v2-client-secret",
    merchantId: "v2-merchant-id",
    entityId: "8ac7a4ca7802ed8e0178176ca52222d0",
    webhookSecret: "separate-webhook-secret",
    checkoutSecret: secret,
    checkoutBaseUrl: "https://testsecure.peachpayments.com",
    authBaseUrl: "https://sandbox-dashboard.peachpayments.com",
    webhookUrl: "https://storefront.example.invalid/hooks/peach",
    storefrontUrl: "http://localhost:3004",
  };
  const fetcher = jest.fn(async (_input: RequestInfo | URL, _init?: RequestInit) => new Response(JSON.stringify(
    signedResponse("000.100.110", { referencedId: captureId }),
  ), { status: 200, headers: { "content-type": "application/json" } }));

  const observation = await peachRefundPayment(config, {
    referencedCaptureId: captureId,
    amountMinor: 500,
    currencyCode: "ZAR",
  }, fetcher as typeof fetch);

  expect(fetcher).toHaveBeenCalledTimes(1);
  expect(fetcher.mock.calls[0]?.[0]).toBe(PEACH_REFUND_URL);
  const init = fetcher.mock.calls[0]?.[1] as RequestInit;
  const body = JSON.parse(String(init.body)) as Record<string, string>;
  expect(init.method).toBe("POST");
  expect(new Headers(init.headers).has("authorization")).toBe(false);
  expect(body).toMatchObject({
    amount: "5.00",
    "authentication.entityId": config.entityId,
    currency: "ZAR",
    id: captureId,
    paymentType: "RF",
  });
  expect(body.signature).toBe(peachCheckoutSignature({
    amount: "5.00",
    "authentication.entityId": config.entityId,
    currency: "ZAR",
    id: captureId,
    paymentType: "RF",
  }, secret));
  expect(observation?.outcome).toBe("succeeded");
});

test("rejects altered or mismatched signed response facts", () => {
  const body = signedResponse("000.100.110");
  expect(parsePeachRefundResponse({ ...body, amount: "4.99" }, secret, {
    referencedCaptureId: captureId, amountMinor: 500, currencyCode: "ZAR",
  })).toBeNull();
  expect(parsePeachRefundResponse(body, "wrong-secret", {
    referencedCaptureId: captureId, amountMinor: 500, currencyCode: "ZAR",
  })).toBeNull();
  expect(parsePeachRefundResponse(signedResponse("000.100.110", { referencedId: "f".repeat(32) }), secret, {
    referencedCaptureId: captureId, amountMinor: 500, currencyCode: "ZAR",
  })).toBeNull();
});

test("only documented definite result codes release the reservation", () => {
  expect(peachRefundOutcome("000.200.000")).toBe("pending");
  expect(peachRefundOutcome("100.550.701")).toBe("failed");
  expect(peachRefundOutcome("700.400.200")).toBe("failed");
  expect(peachRefundOutcome("700.300.100")).toBe("failed");
  expect(peachRefundOutcome("700.300.101")).toBe("unknown");
  expect(peachRefundOutcome("100.100.400")).toBe("unknown");
});

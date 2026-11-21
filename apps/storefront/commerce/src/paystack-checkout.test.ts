import { createHmac } from "node:crypto";
import { PaymentSessionStatus } from "@medusajs/framework/utils";
import {
  createPaystackRefund, majorToMinor, medusaAmountToMinor, parsePaystackRefund, parsePaystackVerifyResponse,
  parsePaystackWebhook, paystackChargeState, paystackRefundOutcome, paystackRefundReference, verifyPaystackWebhookSignature,
} from "./paystack-checkout";
import { paystackPaymentConfig } from "./paystack-payment-config";
import { paystackEventCanAdvance } from "./paystack-payment-store";
import { paystackPaymentSessionStatus } from "./modules/storefront-paystack-payment-provider/service";

const secret = "whsec_test_signing_secret";
function sign(rawBody: Buffer, t: number, key = secret): string {
  return `t=${t},v1=whk_test:${createHmac("sha512", key).update(`${t}.`).update(rawBody).digest("hex")}`;
}

describe("Paystack hosted checkout boundary", () => {
  test("normalizes Medusa major-unit amounts without rounding fractional cents", () => {
    expect(majorToMinor("120.5")).toBe(12050);
    expect(majorToMinor("12.345")).toBeNull();
    expect(majorToMinor(-1)).toBeNull();
    expect(medusaAmountToMinor({ raw: { value: "25.70", precision: 2 }, numeric: 25.7 })).toBe(2570);
    expect(medusaAmountToMinor({ value: "400.00", precision: 20 })).toBe(40000);
  });

  test("verifies the timestamped signature on the exact raw body within the replay window", () => {
    const raw = Buffer.from('{"event":"charge.success","data":{"reference":"dk_reference_1"}}');
    const now = 1_790_000_000;
    const header = sign(raw, now);
    expect(verifyPaystackWebhookSignature({ secret, header, rawBody: raw, nowSeconds: now })).toBe(true);
    expect(verifyPaystackWebhookSignature({ secret, header, rawBody: raw, nowSeconds: now + 300 })).toBe(true);
    expect(verifyPaystackWebhookSignature({ secret, header, rawBody: raw, nowSeconds: now + 301 })).toBe(false);
    expect(verifyPaystackWebhookSignature({ secret, header, rawBody: Buffer.concat([raw, Buffer.from(" ")]), nowSeconds: now })).toBe(false);
    expect(verifyPaystackWebhookSignature({ secret: "whsec_other", header, rawBody: raw, nowSeconds: now })).toBe(false);
    // Rotation: either of two v1 entries may match.
    const rotated = `${sign(raw, now, "whsec_old").split(",")[0]},v1=whk_old:${"0".repeat(128)},${sign(raw, now).split(",")[1]}`;
    expect(verifyPaystackWebhookSignature({ secret, header: rotated, rawBody: raw, nowSeconds: now })).toBe(true);
    // The legacy x-paystack-signature format (no timestamp) is not accepted.
    const legacy = createHmac("sha512", "sk_test_key").update(raw).digest("hex");
    expect(verifyPaystackWebhookSignature({ secret, header: legacy, rawBody: raw, nowSeconds: now })).toBe(false);
    expect(verifyPaystackWebhookSignature({ secret, header: `t=${now},t=${now},v1=x:${"a".repeat(128)}`, rawBody: raw, nowSeconds: now })).toBe(false);
  });

  test("treats webhook bodies only as triggers carrying a reference", () => {
    expect(parsePaystackWebhook(Buffer.from('{"event":"charge.success","data":{"reference":"dk_reference_1","amount":1}}')))
      .toEqual({ event: "charge.success", reference: "dk_reference_1" });
    expect(parsePaystackWebhook(Buffer.from('{"event":"refund.processed","data":{"transaction_reference":"dk_reference_1"}}')))
      .toEqual({ event: "refund", reference: "dk_reference_1" });
    expect(parsePaystackWebhook(Buffer.from('{"event":"transfer.success","data":{}}'))).toEqual({ event: "ignored" });
    expect(parsePaystackWebhook(Buffer.from('{"event":"charge.success","data":{"reference":"x"}}'))).toBeNull();
    expect(parsePaystackWebhook(Buffer.from("not json"))).toBeNull();
  });

  test("normalizes the verify response without retaining customer or card fields", () => {
    const body = {
      status: true, message: "Verification successful",
      data: {
        id: 4099260516, status: "success", reference: "dk_reference_1", amount: 40333, currency: "ZAR",
        paid_at: "2026-11-21T09:15:02.000Z", created_at: "2026-11-21T09:14:24.000Z",
        customer: { email: "private@example.test" }, authorization: { last4: "4081", bin: "408408" }, ip_address: "203.0.113.1",
      },
    };
    const observation = parsePaystackVerifyResponse(body, "dk_reference_1");
    expect(observation).toMatchObject({
      kind: "charge", reference: "dk_reference_1", transaction_id: "4099260516", amount_minor: 40333,
      currency_code: "ZAR", provider_status: "success", event_timestamp: "2026-11-21T09:15:02.000Z",
    });
    expect(JSON.stringify(observation)).not.toMatch(/private@|4081|408408|203\.0\.113/);
    expect(parsePaystackVerifyResponse(body, "dk_reference_2")).toBeNull();
    expect(parsePaystackVerifyResponse({ ...body, status: false }, "dk_reference_1")).toBeNull();
    expect(parsePaystackVerifyResponse({ status: true, data: { ...body.data, amount: "403.33" } }, "dk_reference_1")).toBeNull();
  });

  test("maps charge and refund statuses conservatively", () => {
    expect(paystackChargeState("success")).toBe("paid");
    expect(paystackChargeState("failed")).toBe("declined");
    expect(paystackChargeState("abandoned")).toBe("pending");
    expect(paystackChargeState("ongoing")).toBe("pending");
    expect(paystackChargeState("reversed")).toBe("unknown");
    expect(paystackChargeState("something-new")).toBe("unknown");
    expect(paystackRefundOutcome("processed")).toBe("succeeded");
    expect(paystackRefundOutcome("processing")).toBe("pending");
    expect(paystackRefundOutcome("failed")).toBe("failed");
    expect(paystackRefundOutcome("needs-attention")).toBe("unknown");
  });

  test("derives a stable, valid refund reference from the Firstout request ID", () => {
    expect(paystackRefundReference("6f1c2a5e-0b8d-4c21-9e57-3a4b5c6d7e8f")).toBe("dkr_6f1c2a5e0b8d4c219e573a4b5c6d7e8f");
    expect(paystackRefundReference("6f1c2a5e-0b8d-4c21-9e57-3a4b5c6d7e8f")).toMatch(/^[A-Za-z0-9_-]{8,64}$/);
    expect(() => paystackRefundReference("../../etc")).toThrow();
  });

  test("binds a refund object to the expected charge", () => {
    const listed = { id: 747680, transaction: 627178582, reference: "dkr_abc12345", amount: 10000, currency: "ZAR", status: "processed", created_at: "2026-11-21T10:00:00Z" };
    expect(parsePaystackRefund(listed, { reference: "dk_ref_charge", transactionId: "627178582", refundRequestId: null }))
      .toMatchObject({ provider_refund_id: "747680", refund_reference: "dkr_abc12345", amount_minor: 10000, provider_status: "processed" });
    expect(parsePaystackRefund(listed, { reference: "dk_ref_charge", transactionId: "1", refundRequestId: null })).toBeNull();
    const created = { ...listed, transaction: { id: 627178582, reference: "dk_other_charge" } };
    expect(parsePaystackRefund(created, { reference: "dk_ref_charge", transactionId: null, refundRequestId: null })).toBeNull();
  });

  test("never trusts an unreadable or mismatched refund response and reports duplicates", async () => {
    const config = paystackPaymentConfig({ PAYSTACK_SECRET_KEY: "sk_test_abc", PAYSTACK_WEBHOOK_SECRET: "whsec_abc" })!;
    const requestId = "6f1c2a5e-0b8d-4c21-9e57-3a4b5c6d7e8f";
    const input = { transactionReference: "dk_ref_charge", transactionId: null, amountMinor: 5000, currencyCode: "ZAR", requestId };
    const bodies: unknown[] = [];
    const respond = (status: number, body: unknown) => jest.fn(async (_url: unknown, init?: RequestInit) => {
      bodies.push(JSON.parse(String(init?.body)));
      return new Response(JSON.stringify(body), { status });
    }) as unknown as typeof fetch;
    const data = { id: 3018284, reference: paystackRefundReference(requestId), amount: 5000, currency: "ZAR", status: "pending",
      createdAt: "2026-11-21T09:21:17.122Z", transaction: { id: 1004723697, reference: "dk_ref_charge" } };

    expect(await createPaystackRefund(config, input, respond(200, { status: true, data })))
      .toMatchObject({ kind: "observed", observation: { provider_refund_id: "3018284", refund_request_id: requestId } });
    expect(bodies[0]).toEqual({ transaction: "dk_ref_charge", amount: 5000, currency: "ZAR", reference: paystackRefundReference(requestId) });
    expect(await createPaystackRefund(config, input, respond(409, { status: false }))).toEqual({ kind: "duplicate" });
    expect(await createPaystackRefund(config, input, respond(502, {}))).toMatchObject({ kind: "ambiguous" });
    expect(await createPaystackRefund(config, input, respond(200, { status: true, data: { ...data, amount: 4999 } }))).toMatchObject({ kind: "ambiguous" });
    expect(await createPaystackRefund(config, input, respond(400, { status: false }))).toEqual({ kind: "rejected", status: 400 });
    const offline = jest.fn(async () => { throw new Error("timeout"); }) as unknown as typeof fetch;
    expect(await createPaystackRefund(config, input, offline)).toMatchObject({ kind: "ambiguous" });
  });

  test("reports persisted paid state as captured and keeps unknown pending", () => {
    expect(paystackPaymentSessionStatus("paid")).toBe(PaymentSessionStatus.CAPTURED);
    expect(paystackPaymentSessionStatus("captured")).toBe(PaymentSessionStatus.CAPTURED);
    expect(paystackPaymentSessionStatus("declined")).toBe(PaymentSessionStatus.ERROR);
    expect(paystackPaymentSessionStatus("unknown")).toBe(PaymentSessionStatus.PENDING);
  });

  test("a stale observation cannot downgrade a captured payment after waiting for the lock", () => {
    const captured = { status: "captured", last_event_timestamp: "2026-11-20T14:33:58Z" };
    expect(paystackEventCanAdvance(captured, { event_timestamp: "2026-11-20T14:33:57Z", result_state: "pending" })).toBe(false);
    expect(paystackEventCanAdvance(captured, { event_timestamp: "2026-11-20T14:33:59Z", result_state: "declined" })).toBe(false);
    expect(paystackEventCanAdvance(captured, { event_timestamp: "2026-11-20T14:33:59Z", result_state: "paid" })).toBe(true);
  });

  test("stays disabled until fully configured and only accepts a live key when explicitly allowed", () => {
    const base = { PAYSTACK_SECRET_KEY: "sk_test_abc123", PAYSTACK_WEBHOOK_SECRET: "whsec_abc", STOREFRONT_PUBLIC_URL: "https://shop.example.test" };
    expect(paystackPaymentConfig({})).toBeNull();
    expect(() => paystackPaymentConfig({ PAYSTACK_SECRET_KEY: "sk_test_abc123" })).toThrow(/incomplete/i);
    expect(paystackPaymentConfig(base)).toMatchObject({
      mode: "test", callbackUrl: "https://shop.example.test/checkout/paystack-return", refundsPaused: false,
    });
    expect(() => paystackPaymentConfig({ ...base, PAYSTACK_SECRET_KEY: "pk_test_abc123" })).toThrow(/secret key/i);
    expect(() => paystackPaymentConfig({ ...base, PAYSTACK_WEBHOOK_SECRET: "sk_test_abc123" })).toThrow(/whsec_/);
    expect(() => paystackPaymentConfig({ ...base, PAYSTACK_SECRET_KEY: "sk_live_abc123" })).toThrow(/PAYSTACK_LIVE_ENABLED/);
    expect(paystackPaymentConfig({ ...base, PAYSTACK_SECRET_KEY: "sk_live_abc123", PAYSTACK_LIVE_ENABLED: "true" })?.mode).toBe("live");
    expect(() => paystackPaymentConfig({ ...base, PAYSTACK_SECRET_KEY: "sk_live_abc123", PAYSTACK_LIVE_ENABLED: "true",
      STOREFRONT_PUBLIC_URL: "http://localhost:3004" })).toThrow(/HTTPS/);
    expect(() => paystackPaymentConfig({ ...base, STOREFRONT_PUBLIC_URL: "http://shop.example.test" })).toThrow(/HTTPS/);
    expect(() => paystackPaymentConfig({ ...base, STOREFRONT_PUBLIC_URL: "https://shop.example.test/?next=x" })).toThrow(/query/);
    expect(paystackPaymentConfig({ ...base, PAYSTACK_REFUNDS_PAUSED: "true" })?.refundsPaused).toBe(true);
  });
});

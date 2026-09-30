import { createHmac } from "node:crypto";
import {
  majorToMinor,
  medusaAmountToMinor,
  parsePeachWebhook,
  parsePeachStatusResponse,
  peachResultState,
  verifyPeachWebhookSignature,
} from "./peach-checkout";
import { peachPaymentConfig } from "./peach-payment-config";
import { peachEventCanAdvance } from "./peach-payment-store";
import { peachPaymentSessionStatus } from "./modules/storefront-peach-payment-provider/service";
import { PaymentSessionStatus } from "@medusajs/framework/utils";

describe("Peach Hosted Checkout V2 boundary", () => {
  test("normalizes major-unit amounts without rounding fractional cents", () => {
    expect(majorToMinor("120.5")).toBe(12050);
    expect(majorToMinor("0.00")).toBe(0);
    expect(majorToMinor(12.34)).toBe(1234);
    expect(majorToMinor("12.3400")).toBe(1234);
    expect(majorToMinor("12.345")).toBeNull();
    expect(majorToMinor(-1)).toBeNull();
    expect(majorToMinor("1e3")).toBeNull();
    expect(medusaAmountToMinor({ raw: { value: "25.70", precision: 2 }, numeric: 25.7 })).toBe(2570);
    expect(medusaAmountToMinor({ raw: { value: "25.701", precision: 3 }, numeric: 25.701 })).toBeNull();
  });

  test("verifies the exact configured URL and raw form body before parsing", () => {
    const secret = "webhook-secret";
    const url = "https://commerce.example.test/hooks/peach";
    const timestamp = "2025-11-20T14:33:57Z";
    const webhookId = "webhook-1";
    const raw = Buffer.from("amount=10.00&checkoutId=checkout-1&paymentType=DB&result_code=000.100.110");
    const signature = createHmac("sha256", secret).update(`${timestamp}.${webhookId}.${url}.${raw.toString("utf8")}`).digest("hex");
    const input = { secret, configuredUrl: url, timestamp, webhookId, signature, algorithm: "HmacSHA256", rawBody: raw };

    expect(verifyPeachWebhookSignature(input)).toBe(true);
    expect(verifyPeachWebhookSignature({ ...input, configuredUrl: `${url}/` })).toBe(false);
    expect(verifyPeachWebhookSignature({ ...input, rawBody: Buffer.concat([raw, Buffer.from(" ")]) })).toBe(false);
    expect(verifyPeachWebhookSignature({ ...input, algorithm: "sha256" })).toBe(false);
  });

  test("normalizes the documented flat V2 status response without retaining cardholder fields", () => {
    const status = parsePeachStatusResponse({
      amount: "10.00", checkoutId: "checkout-1", currency: "ZAR", id: "txn-1",
      merchantTransactionId: "Abc12345", paymentType: "DB", "result.code": "000.100.110",
      timestamp: "2025-11-20T14:33:57Z", "card.holder": "Private Name", "customer.email": "private@example.test",
    });
    expect(status).toMatchObject({
      webhook_id: null, checkout_id: "checkout-1", merchant_reference: "Abc12345", amount_minor: 1000,
      currency_code: "ZAR", payment_type: "DB", result_code: "000.100.110", transaction_id: "txn-1",
    });
    expect(Object.keys(status || {}).sort()).toEqual([
      "amount_minor", "canonical_sha256", "checkout_id", "currency_code", "event_timestamp",
      "merchant_reference", "payment_type", "raw_sha256", "result_code", "transaction_id", "webhook_id",
    ]);
    expect(parsePeachStatusResponse({
      amount: "10.00", checkoutId: "checkout-1", currency: "ZAR", merchantTransactionId: "Abc12345",
      paymentType: "DB", "result.code": "000.100.110", result: { code: "800.100.153" },
      timestamp: "2025-11-20T14:33:57Z",
    })).toBeNull();
  });

  test("persists only normalized allowlisted callback fields and rejects conflicting result aliases", () => {
    const raw = Buffer.from([
      "amount=10.00", "checkoutId=checkout-1", "currency=zar", "merchantTransactionId=Abc12345",
      "paymentType=DB", "result.code=000.100.110", "result_code=000.100.110", "timestamp=2025-11-20T14%3A33%3A57Z",
      "card.holder=Sensitive+Name", "card.last4Digits=1234", "customer.email=private%40example.test",
    ].join("&"));
    const event = parsePeachWebhook(raw, "webhook-1");
    expect(event).toMatchObject({
      webhook_id: "webhook-1", checkout_id: "checkout-1", merchant_reference: "Abc12345",
      amount_minor: 1000, currency_code: "ZAR", payment_type: "DB", result_code: "000.100.110",
    });
    expect(event?.raw_sha256).toMatch(/^[a-f\d]{64}$/);
    expect(Object.keys(event || {}).sort()).toEqual([
      "amount_minor", "canonical_sha256", "checkout_id", "currency_code", "event_timestamp",
      "merchant_reference", "payment_type", "raw_sha256", "result_code", "transaction_id", "webhook_id",
    ]);
    expect(event).not.toHaveProperty("card");
    expect(event).not.toHaveProperty("customer");

    const conflicting = Buffer.from(`${raw.toString("utf8")}&result_code=800.100.153`);
    expect(parsePeachWebhook(conflicting, "webhook-2")).toBeNull();
    expect(parsePeachWebhook(raw, "")).toBeNull();
  });

  test("does not promote RF or uncertain, cancelled, and unrecognized results to paid", () => {
    expect(peachResultState("000.100.110", "DB")).toBe("paid");
    expect(peachResultState("000.400.110", "DB")).toBe("paid");
    expect(peachResultState("000.500.100", "DB")).toBe("paid");
    expect(peachResultState("000.500.999", "DB")).toBe("unknown");
    expect(peachResultState("000.100.110", "RF")).toBe("unknown");
    expect(peachResultState("100.396.104", "DB")).toBe("unknown");
    expect(peachResultState("100.396.101", "DB")).toBe("cancelled");
    expect(peachResultState("900.100.300", "DB")).toBe("unknown");
    expect(peachResultState("800.500.100", "DB")).toBe("unknown");
    expect(peachResultState("800.700.100", "DB")).toBe("pending");
    expect(peachResultState("800.700.101", "DB")).toBe("declined");
    expect(peachResultState("000.400.050", "DB")).toBe("unknown");
    expect(peachResultState("800.100.153", "DB")).toBe("declined");
    expect(peachResultState("000.200.100", "DB")).toBe("pending");
  });

  test("reports persisted paid state as captured and preserves unknown as pending", () => {
    expect(peachPaymentSessionStatus("paid")).toBe(PaymentSessionStatus.CAPTURED);
    expect(peachPaymentSessionStatus("captured")).toBe(PaymentSessionStatus.CAPTURED);
    expect(peachPaymentSessionStatus("pending")).toBe(PaymentSessionStatus.PENDING);
    expect(peachPaymentSessionStatus("unknown")).toBe(PaymentSessionStatus.PENDING);
  });

  test("a stale callback cannot downgrade a captured paid exception after waiting for the lock", () => {
    const paidExceptionSnapshot = { status: "captured", last_event_timestamp: "2025-11-20T14:33:58Z" };
    expect(peachEventCanAdvance(paidExceptionSnapshot, {
      event_timestamp: "2025-11-20T14:33:57Z", result_state: "pending",
    })).toBe(false);
    expect(peachEventCanAdvance(paidExceptionSnapshot, {
      event_timestamp: "2025-11-20T14:33:59Z", result_state: "cancelled",
    })).toBe(false);
    expect(peachEventCanAdvance(paidExceptionSnapshot, {
      event_timestamp: "2025-11-20T14:33:59Z", result_state: "paid",
    })).toBe(true);
  });

  test("keeps configuration disabled until all sandbox credentials and URLs are explicit", () => {
    expect(peachPaymentConfig({})).toBeNull();
    expect(() => peachPaymentConfig({ PEACH_CLIENT_ID: "only-one" })).toThrow(/incomplete/i);
    const config = peachPaymentConfig({
      PEACH_ENVIRONMENT: "sandbox",
      PEACH_CLIENT_ID: "client", PEACH_CLIENT_SECRET: "secret", PEACH_MERCHANT_ID: "merchant",
      PEACH_ENTITY_ID: "entity", PEACH_WEBHOOK_SECRET: "hook-secret",
      PEACH_WEBHOOK_URL: "https://commerce.example.test/hooks/peach",
      STOREFRONT_PUBLIC_URL: "https://shop.example.test",
    });
    expect(config?.checkoutBaseUrl).toBe("https://testsecure.peachpayments.com");
    expect(() => peachPaymentConfig({
      PEACH_ENVIRONMENT: "production",
      PEACH_CLIENT_ID: "client", PEACH_CLIENT_SECRET: "secret", PEACH_MERCHANT_ID: "merchant",
      PEACH_ENTITY_ID: "entity", PEACH_WEBHOOK_SECRET: "hook-secret",
      PEACH_WEBHOOK_URL: "https://commerce.example.test/hooks/peach",
    })).toThrow(/sandbox-only/i);
  });
});

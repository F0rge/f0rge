import { createHmac, randomUUID } from "node:crypto";
import { parsePeachWebhook, verifyPeachWebhookSignature, type PeachWebhookEvent } from "./peach-checkout";
import { peachRefundOutcome } from "./peach-refunds";
import { customerRefundStatusProjection } from "./storefront-peach-refunds";

test("pure customer refund projection upgrades a decline and ignores stale or duplicate callbacks", () => {
  const order = { email: "refund-fixture@example.invalid", display_id: 754 };
  let metadata: Record<string, unknown> = {};
  const webhookUrl = "https://storefront.example.invalid/hooks/peach";
  const webhookSecret = "test-webhook-signing-secret";
  const providerRefundId = "8ac7a49f8af08e94018af09246760e30";
  const captureId = "8ac7a4a284c684140184c7a8f19a5530";
  const signedEvent = (resultCode: string): PeachWebhookEvent => {
    const timestamp = new Date().toISOString();
    const webhookId = `refund-projection-${randomUUID()}`;
    const rawBody = new URLSearchParams({
      amount: "5.00",
      currency: "ZAR",
      id: providerRefundId,
      referencedId: captureId,
      paymentType: "RF",
      result_code: resultCode,
      timestamp,
    }).toString();
    const signature = createHmac("sha256", webhookSecret)
      .update(`${timestamp}.${webhookId}.${webhookUrl}.${rawBody}`)
      .digest("hex");
    expect(verifyPeachWebhookSignature({
      secret: webhookSecret,
      configuredUrl: webhookUrl,
      timestamp,
      webhookId,
      signature,
      algorithm: "HMAC-SHA256",
      rawBody,
    })).toBe(true);
    const event = parsePeachWebhook(rawBody, webhookId);
    if (!event) throw new Error("Signed refund projection fixture did not parse");
    return event;
  };
  const failure = signedEvent("100.550.701");
  const success = signedEvent("000.100.110");
  const failureStatus = peachRefundOutcome(failure.result_code);
  const successStatus = peachRefundOutcome(success.result_code);
  if (failureStatus !== "failed" || successStatus !== "succeeded") {
    throw new Error("Refund status fixture uses an unexpected Peach outcome");
  }

  metadata = customerRefundStatusProjection(metadata, order, failure, failureStatus) || metadata;
  expect((metadata.storefront_refunds as { status: string }[])[0]?.status).toBe("failed");

  metadata = customerRefundStatusProjection(metadata, order, success, successStatus) || metadata;
  const afterSuccess = metadata;
  metadata = customerRefundStatusProjection(metadata, order, success, successStatus) || metadata;
  metadata = customerRefundStatusProjection(metadata, order, failure, failureStatus) || metadata;

  const projectedRefunds = metadata.storefront_refunds as {
    provider_refund_id: string; amount_minor: number; status: string;
  }[];
  const outbox = metadata.storefront_notification_outbox as {
    id: string; data: { refund: { status: string } };
  }[];
  expect(projectedRefunds).toEqual([{
    provider_refund_id: providerRefundId,
    amount_minor: 500,
    currency_code: "ZAR",
    status: "succeeded",
  }]);
  expect(outbox.map((entry) => entry.data.refund.status)).toEqual(["failed", "succeeded"]);
  expect(new Set(outbox.map((entry) => entry.id)).size).toBe(2);
  expect(customerRefundStatusProjection(afterSuccess, order, success, successStatus)).toBeNull();
  expect(customerRefundStatusProjection(afterSuccess, order, failure, failureStatus)).toBeNull();
});

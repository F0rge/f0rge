import { parsePaystackRefund, paystackRefundOutcome } from "./paystack-checkout";
import { customerRefundStatusProjection } from "./storefront-paystack-refunds";

test("pure customer refund projection upgrades a decline and ignores stale or duplicate observations", () => {
  const order = { email: "refund-fixture@example.invalid", display_id: 754 };
  let metadata: Record<string, unknown> = {};
  const observed = (status: string) => {
    const event = parsePaystackRefund({
      id: 3018284, transaction: 4099260516, reference: "dkr_00000000000000000000000000000754",
      amount: 500, currency: "ZAR", status, createdAt: "2026-10-01T12:30:00.000Z",
    }, { reference: "dk_capture754", transactionId: "4099260516", refundRequestId: null });
    if (!event) throw new Error("Refund projection fixture did not parse");
    return event;
  };
  const failure = observed("failed");
  const success = observed("processed");
  const failureStatus = paystackRefundOutcome(failure.provider_status);
  const successStatus = paystackRefundOutcome(success.provider_status);
  if (failureStatus !== "failed" || successStatus !== "succeeded") {
    throw new Error("Refund status fixture uses an unexpected Paystack outcome");
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
    provider_refund_id: "3018284",
    amount_minor: 500,
    currency_code: "ZAR",
    status: "succeeded",
  }]);
  expect(outbox.map((entry) => entry.data.refund.status)).toEqual(["failed", "succeeded"]);
  expect(new Set(outbox.map((entry) => entry.id)).size).toBe(2);
  expect(customerRefundStatusProjection(afterSuccess, order, success, successStatus)).toBeNull();
  expect(customerRefundStatusProjection(afterSuccess, order, failure, failureStatus)).toBeNull();
});

import { model } from "@medusajs/framework/utils";

/** Normalized facts read from Paystack's API, triggered by a signed webhook, a status poll, or a refund response. */
const PaystackWebhookInbox = model.define("storefront_paystack_webhook_inbox", {
  id: model.id({ prefix: "spwh" }).primaryKey(),
  event_key: model.text().unique(),
  source: model.text(),
  kind: model.text(),
  reference: model.text(),
  transaction_id: model.text().nullable(),
  provider_refund_id: model.text().nullable(),
  refund_reference: model.text().nullable(),
  refund_request_id: model.text().nullable(),
  amount_minor: model.bigNumber(),
  currency_code: model.text(),
  provider_status: model.text(),
  result_state: model.text(),
  event_timestamp: model.text(),
  raw_sha256: model.text(),
  canonical_sha256: model.text(),
  signature_sha256: model.text().nullable(),
  status: model.text(),
  attempt_count: model.number(),
  next_attempt_at: model.dateTime().nullable(),
  lease_until: model.dateTime().nullable(),
  lease_token: model.text().nullable(),
  last_error_code: model.text().nullable(),
  processed_at: model.dateTime().nullable(),
});

export default PaystackWebhookInbox;

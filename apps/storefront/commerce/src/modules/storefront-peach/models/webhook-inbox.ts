import { model } from "@medusajs/framework/utils";

const PeachWebhookInbox = model.define("storefront_peach_webhook_inbox", {
  id: model.id({ prefix: "spwh" }).primaryKey(),
  event_key: model.text().unique(),
  source: model.text(),
  webhook_id: model.text().unique().nullable(),
  checkout_id: model.text(),
  merchant_reference: model.text(),
  amount_minor: model.bigNumber(),
  currency_code: model.text(),
  payment_type: model.text(),
  result_code: model.text(),
  transaction_id: model.text().nullable(),
  event_timestamp: model.text(),
  result_state: model.text(),
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

export default PeachWebhookInbox;

import { model } from "@medusajs/framework/utils";

const PeachPaymentAttempt = model.define("storefront_peach_payment_attempt", {
  id: model.id({ prefix: "spay" }).primaryKey(),
  payment_session_id: model.text().unique(),
  merchant_reference: model.text().unique(),
  nonce: model.text().unique(),
  checkout_id: model.text().unique().nullable(),
  amount_minor: model.bigNumber(),
  currency_code: model.text(),
  status: model.text(),
  redirect_url: model.text().nullable(),
  last_event_timestamp: model.text().nullable(),
  last_event_state: model.text().nullable(),
  last_status_checked_at: model.dateTime().nullable(),
});

export default PeachPaymentAttempt;

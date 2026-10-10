import { model } from "@medusajs/framework/utils";

const PeachPaymentAttempt = model.define("storefront_peach_payment_attempt", {
  id: model.id({ prefix: "spay" }).primaryKey(),
  payment_session_id: model.text().unique(),
  cart_id: model.text().nullable(),
  checkout_snapshot: model.json().nullable(),
  merchant_reference: model.text().unique(),
  nonce: model.text().unique(),
  checkout_id: model.text().unique().nullable(),
  captured_transaction_id: model.text().nullable(),
  captured_order_id: model.text().nullable(),
  amount_minor: model.bigNumber(),
  currency_code: model.text(),
  status: model.text(),
  redirect_url: model.text().nullable(),
  last_event_timestamp: model.text().nullable(),
  last_event_state: model.text().nullable(),
  last_status_checked_at: model.dateTime().nullable(),
}).indexes([
  {
    name: "IDX_storefront_peach_payment_attempt_captured_transaction_id",
    on: ["captured_transaction_id"],
    where: { captured_transaction_id: { $ne: null } },
  },
  {
    name: "IDX_storefront_peach_payment_attempt_captured_order_id",
    on: ["captured_order_id"],
    where: { captured_order_id: { $ne: null } },
  },
]);

export default PeachPaymentAttempt;

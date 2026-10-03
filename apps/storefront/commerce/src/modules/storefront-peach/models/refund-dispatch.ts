import { model } from "@medusajs/framework/utils";

const PeachRefundDispatch = model.define("storefront_peach_refund_dispatch", {
  id: model.id({ prefix: "srefund" }).primaryKey(),
  request_id: model.text().unique(),
  handoff_id: model.text().nullable(),
  external_order_id: model.text(),
  original_transaction_id: model.text(),
  amount_minor: model.bigNumber(),
  currency_code: model.text(),
  cancel_order: model.boolean().default(false),
  allocation: model.json().default({}),
  status: model.text(),
  firstout_status: model.text().nullable(),
  provider_refund_id: model.text().unique().nullable(),
  provider_result_code: model.text().nullable(),
  canonical_sha256: model.text().nullable(),
  medusa_payment_id: model.text().nullable(),
  medusa_refund_id: model.text().nullable(),
  authorization_key: model.text().nullable(),
});

export default PeachRefundDispatch;

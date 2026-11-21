import { MedusaService } from "@medusajs/framework/utils";
import PaystackPaymentAttempt from "./models/payment-attempt";
import PaystackRefundDispatch from "./models/refund-dispatch";
import PaystackWebhookInbox from "./models/webhook-inbox";

class StorefrontPaystackService extends MedusaService({ PaystackPaymentAttempt, PaystackRefundDispatch, PaystackWebhookInbox }) {}

export default StorefrontPaystackService;

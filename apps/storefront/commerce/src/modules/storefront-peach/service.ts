import { MedusaService } from "@medusajs/framework/utils";
import PeachPaymentAttempt from "./models/payment-attempt";
import PeachRefundDispatch from "./models/refund-dispatch";
import PeachWebhookInbox from "./models/webhook-inbox";

class StorefrontPeachService extends MedusaService({ PeachPaymentAttempt, PeachRefundDispatch, PeachWebhookInbox }) {}

export default StorefrontPeachService;

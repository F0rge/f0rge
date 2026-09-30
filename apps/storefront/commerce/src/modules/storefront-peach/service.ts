import { MedusaService } from "@medusajs/framework/utils";
import PeachPaymentAttempt from "./models/payment-attempt";
import PeachWebhookInbox from "./models/webhook-inbox";

class StorefrontPeachService extends MedusaService({ PeachPaymentAttempt, PeachWebhookInbox }) {}

export default StorefrontPeachService;

import { ModuleProvider, Modules } from "@medusajs/framework/utils";
import { StorefrontPeachPaymentProvider } from "./service";

export default ModuleProvider(Modules.PAYMENT, { services: [StorefrontPeachPaymentProvider] });

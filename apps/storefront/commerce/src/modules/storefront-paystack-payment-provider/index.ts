import { ModuleProvider, Modules } from "@medusajs/framework/utils";
import { StorefrontPaystackPaymentProvider } from "./service";

export default ModuleProvider(Modules.PAYMENT, { services: [StorefrontPaystackPaymentProvider] });

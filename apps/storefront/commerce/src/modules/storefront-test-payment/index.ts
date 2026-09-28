import { ModuleProvider, Modules } from "@medusajs/framework/utils";
import { StorefrontTestPaymentProvider } from "./service";

export default ModuleProvider(Modules.PAYMENT, { services: [StorefrontTestPaymentProvider] });

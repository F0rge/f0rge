import { ModuleProvider, Modules } from "@medusajs/framework/utils";
import { StorefrontFulfillmentProvider } from "./service";

export default ModuleProvider(Modules.FULFILLMENT, { services: [StorefrontFulfillmentProvider] });

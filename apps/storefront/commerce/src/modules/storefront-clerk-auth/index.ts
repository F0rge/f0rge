import { ModuleProvider, Modules } from "@medusajs/framework/utils";
import { StorefrontClerkAuthProvider } from "./service";

export default ModuleProvider(Modules.AUTH, { services: [StorefrontClerkAuthProvider] });

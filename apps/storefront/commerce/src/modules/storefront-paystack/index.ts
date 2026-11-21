import { Module } from "@medusajs/framework/utils";
import StorefrontPaystackService from "./service";

export const STOREFRONT_PAYSTACK_MODULE = "storefrontPaystack";

export default Module(STOREFRONT_PAYSTACK_MODULE, { service: StorefrontPaystackService });

import { Module } from "@medusajs/framework/utils";
import StorefrontPeachService from "./service";

export const STOREFRONT_PEACH_MODULE = "storefrontPeach";

export default Module(STOREFRONT_PEACH_MODULE, { service: StorefrontPeachService });

import { MedusaError } from "@medusajs/framework/utils";

// SARS lists the standard South African VAT rate; admins can override this in the local server env.
export function southAfricaVatRate(source = process.env.STOREFRONT_VAT_RATE_PERCENT): number {
  const rate = source === undefined || source === "" ? 15 : Number(source);
  if (!Number.isFinite(rate) || rate < 0 || rate > 100 || Math.round(rate * 100) !== rate * 100) {
    throw new MedusaError(MedusaError.Types.INVALID_DATA, "STOREFRONT_VAT_RATE_PERCENT must be a percentage with at most two decimals");
  }
  return rate;
}

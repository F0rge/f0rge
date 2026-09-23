import { z } from "@medusajs/framework/zod";
import { MedusaError } from "@medusajs/framework/utils";

const productSchema = z.object({
  source_sku_id: z.string().uuid(),
  sku: z.string().min(1),
  name: z.string().min(1),
  price_minor_zar: z.number().int().positive(),
  available_quantity: z.number().int().nonnegative(),
  revision: z.string().min(1),
  observed_at: z.string().min(1),
}).strict();

const responseSchema = z.object({
  company_id: z.string().uuid(),
  products: z.array(productSchema),
}).strict();

export type OpsProduct = z.infer<typeof productSchema>;
export type OpsProductsResponse = z.infer<typeof responseSchema>;

export function parseOpsProducts(value: unknown, expectedCompanyId: string): OpsProductsResponse {
  const parsed = responseSchema.parse(value);
  if (parsed.company_id !== expectedCompanyId) {
    throw new MedusaError(MedusaError.Types.INVALID_DATA, "Ops Commerce returned a different company");
  }
  if (new Set(parsed.products.map((product) => product.source_sku_id)).size !== parsed.products.length) {
    throw new MedusaError(MedusaError.Types.INVALID_DATA, "Ops Commerce returned duplicate source SKUs");
  }
  return parsed;
}

// Medusa v2 stores prices in major units; the Ops wire contract uses exact ZAR cents.
export function medusaPrice(priceMinorZar: number): number {
  if (!Number.isSafeInteger(priceMinorZar) || priceMinorZar <= 0) {
    throw new MedusaError(MedusaError.Types.INVALID_DATA, "Invalid ZAR minor-unit price");
  }
  return priceMinorZar / 100;
}

export function shouldApplyRevision(incoming: string, applied: unknown): boolean {
  return typeof applied !== "string" || incoming > applied;
}

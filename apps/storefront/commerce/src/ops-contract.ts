import { z } from "@medusajs/framework/zod";
import { MedusaError } from "@medusajs/framework/utils";

const productSchema = z.object({
  source_sku_id: z.string().uuid(),
  product_group_id: z.string().uuid().nullable(),
  product_title: z.string().min(1).nullable(),
  options: z.record(z.string(), z.string().min(1)),
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
  if (new Set(parsed.products.map((product) => product.sku)).size !== parsed.products.length) {
    throw new MedusaError(MedusaError.Types.INVALID_DATA, "Ops Commerce returned duplicate SKU codes");
  }
  const combinations = new Set<string>();
  const groupTitles = new Map<string, string>();
  const groupOptionKeys = new Map<string, string>();
  for (const product of parsed.products) {
    if (!product.product_group_id) {
      if (product.product_title || Object.keys(product.options).length) {
        throw new MedusaError(MedusaError.Types.INVALID_DATA, "Ungrouped SKU has group merchandising fields");
      }
      continue;
    }
    if (!product.product_title || !Object.keys(product.options).length ||
      Object.entries(product.options).some(([key, value]) => !key.trim() || !value.trim())) {
      throw new MedusaError(MedusaError.Types.INVALID_DATA, "Grouped SKU needs a title and complete options");
    }
    const keys = Object.keys(product.options).sort().join("\u0000");
    const previousKeys = groupOptionKeys.get(product.product_group_id);
    if (previousKeys && previousKeys !== keys) {
      throw new MedusaError(MedusaError.Types.INVALID_DATA, "Group variants have inconsistent option keys");
    }
    groupOptionKeys.set(product.product_group_id, keys);
    const previousTitle = groupTitles.get(product.product_group_id);
    if (previousTitle && previousTitle !== product.product_title) {
      throw new MedusaError(MedusaError.Types.INVALID_DATA, "Group variants have inconsistent titles");
    }
    groupTitles.set(product.product_group_id, product.product_title);
    const combination = `${product.product_group_id}:${JSON.stringify(Object.entries(product.options).sort())}`;
    if (combinations.has(combination)) {
      throw new MedusaError(MedusaError.Types.INVALID_DATA, "Group variants have duplicate option combinations");
    }
    combinations.add(combination);
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

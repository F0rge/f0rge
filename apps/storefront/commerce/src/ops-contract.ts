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
  acknowledged_commitment_ids: z.array(z.string().min(1)),
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

export type PendingCommitment = {
  commitment_id: string;
  source_sku_id: string;
  quantity: number;
  acknowledged_revision?: string;
};

const pendingCommitmentSchema = z.array(z.object({
  commitment_id: z.string().min(1),
  source_sku_id: z.string().uuid(),
  quantity: z.number().int().positive(),
  acknowledged_revision: z.string().min(1).optional(),
}).strict());

/** Kept on the Medusa variant until the later paid-order importer reconciles it. */
export function pendingCommitments(metadata: Record<string, unknown> | null): PendingCommitment[] {
  const value = metadata?.pending_paid_commitments;
  if (value === undefined) return [];
  const parsed = pendingCommitmentSchema.parse(value);
  if (new Set(parsed.map((item) => item.commitment_id)).size !== parsed.length) {
    throw new MedusaError(MedusaError.Types.INVALID_DATA, "Duplicate pending paid commitment");
  }
  return parsed;
}

/** The latest acknowledged revision prevents an older snapshot resurrecting stock. */
export function projectAvailableQuantity(
  row: OpsProduct,
  pending: PendingCommitment[],
): number {
  const relevant = pending.filter((item) => item.source_sku_id === row.source_sku_id);
  if (relevant.some((item) => item.acknowledged_revision && row.revision < item.acknowledged_revision)) {
    throw new MedusaError(MedusaError.Types.INVALID_DATA, "Operational stock snapshot predates a paid commitment acknowledgement");
  }
  const acknowledged = new Set(row.acknowledged_commitment_ids);
  const unacknowledged = relevant.filter((item) => !acknowledged.has(item.commitment_id));
  if (unacknowledged.some((item) => !Number.isSafeInteger(item.quantity) || item.quantity < 1)) {
    throw new MedusaError(MedusaError.Types.INVALID_DATA, "Invalid pending commitment quantity");
  }
  return Math.max(0, row.available_quantity - unacknowledged.reduce((sum, item) => sum + item.quantity, 0));
}

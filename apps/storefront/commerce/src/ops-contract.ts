import { z } from "@medusajs/framework/zod";
import { MedusaError } from "@medusajs/framework/utils";
import { STOREFRONT_CATEGORIES } from "./catalogue-collections";

const shopCategoryHandles = STOREFRONT_CATEGORIES.map((category) => category.handle) as [string, ...string[]];
const photoToken = z.string().regex(/^[0-9a-f]{64}$/);
const centimetres = z.number().finite().positive().nullable();

const madeToOrderOfferSchema = z.object({
  id: z.string().uuid(),
  capacity: z.number().int().nonnegative(),
  min_lead_time_days: z.number().int().positive(),
  max_lead_time_days: z.number().int().positive(),
  expires_at: z.string().datetime({ offset: true }),
}).strict().refine((offer) => offer.max_lead_time_days >= offer.min_lead_time_days, {
  message: "Made-to-order maximum lead time must not be shorter than its minimum",
});

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
  made_to_order_offer: madeToOrderOfferSchema.nullable(),
  // Opaque; changes only when the SKU's Firstout photo changes. Null when it has none.
  // Absent (a Firstout release older than this commerce) means no photo info: photos are left alone.
  photo_token: photoToken.nullable().optional(),
  // The version 2 request gets ordered SHA-256s of the immutable JPEG bytes.
  gallery_photo_tokens: z.array(photoToken).length(3).optional().refine(
    (tokens) => !tokens || new Set(tokens).size === tokens.length,
    "Gallery photo tokens must be distinct",
  ),
  // Opt-in only. An older source omits these fields. Null removes the corresponding photo.
  setting_photo_token: photoToken.nullable().optional(),
  detail_photo_token: photoToken.nullable().optional(),
  second_detail_photo_token: photoToken.nullable().optional(),
  dimensions_cm: z.object({
    width: centimetres, depth: centimetres, height: centimetres, diameter: centimetres,
  }).strict().nullable().optional(),
  piece_count: z.number().int().positive().nullable().optional(),
  // Opt-in finish colour for the shop card dot. Null clears it; absent (an older Firstout)
  // leaves the stored colour alone.
  swatch_hex: z.string().regex(/^#[0-9a-f]{6}$/).nullable().optional(),
  // One of the four shop categories, from Firstout's mapping. Absent (auto-publish off, or an
  // older Firstout) means categories are left alone.
  shop_category: z.enum(shopCategoryHandles).optional(),
}).strict().refine(
  ({ gallery_photo_tokens: studio, setting_photo_token: setting }) =>
    !setting || (studio !== undefined && !studio.includes(setting)),
  { path: ["setting_photo_token"], message: "A setting photo requires three distinct studio photos" },
).refine(
  ({ gallery_photo_tokens: studio, setting_photo_token: setting, detail_photo_token: detail }) =>
    !detail || (studio !== undefined && !studio.includes(detail) && detail !== setting),
  { path: ["detail_photo_token"], message: "A detail photo requires three distinct studio photos and differs from the setting photo" },
).refine(
  ({ gallery_photo_tokens: studio, setting_photo_token: setting, detail_photo_token: detail, second_detail_photo_token: second }) =>
    !second || (studio !== undefined && Boolean(detail) && !studio.includes(second) && second !== setting && second !== detail),
  { path: ["second_detail_photo_token"], message: "A second detail photo requires a first detail photo and differs from all other photos" },
);

const responseSchema = z.object({
  company_id: z.string().uuid(),
  products: z.array(productSchema),
  curated_catalogue: z.boolean().optional(),
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
  const groupCategories = new Map<string, string | undefined>();
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
    if (groupCategories.has(product.product_group_id) && groupCategories.get(product.product_group_id) !== product.shop_category) {
      throw new MedusaError(MedusaError.Types.INVALID_DATA, "Group variants have inconsistent shop categories");
    }
    groupCategories.set(product.product_group_id, product.shop_category);
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

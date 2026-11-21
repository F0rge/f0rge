import type { MedusaContainer } from "@medusajs/framework/types";
import { ContainerRegistrationKeys } from "@medusajs/framework/utils";
import { createProductCategoriesWorkflow } from "@medusajs/medusa/core-flows";

export const CATALOGUE_COLLECTION_HANDLE = "on-sale";
export const CATALOGUE_COLLECTION_TITLE = "On Sale";
export const LEGACY_CATALOGUE_COLLECTION_HANDLE = "in-stock";

// Owner decision, 21 Nov 2026. Staff assign products to these in Medusa Admin;
// the Firstout sync never writes or clears product categories.
export const STOREFRONT_CATEGORIES = [
  { handle: "sofas-armchairs", name: "Sofas & Armchairs" },
  { handle: "dining-room", name: "Dining Room" },
  { handle: "bedroom", name: "Bedroom" },
  { handle: "coffee-console-tables", name: "Coffee & Console Tables" },
] as const;

export type CollectionRecord = { id: string; handle: string; title: string };

export type CollectionEnsurePlan =
  | { action: "keep"; id: string }
  | { action: "retitle"; id: string }
  | { action: "rename"; id: string }
  | { action: "create" };

export function collectionEnsurePlan(
  rows: CollectionRecord[],
  handle: string,
  title: string,
  legacyHandle?: string,
): CollectionEnsurePlan {
  const current = rows.find((row) => row.handle === handle);
  if (current) return current.title === title ? { action: "keep", id: current.id } : { action: "retitle", id: current.id };
  const legacy = legacyHandle ? rows.find((row) => row.handle === legacyHandle) : undefined;
  if (legacy) return { action: "rename", id: legacy.id };
  return { action: "create" };
}

/**
 * Creates any of the four categories that are missing, by handle. Existing
 * categories are left exactly as staff configured them. Medusa defaults a new
 * category to inactive; the Store API drops internal categories from products
 * and filters by category only when it is active, so both flags are explicit.
 */
export async function ensureStorefrontCategories(container: MedusaContainer): Promise<number> {
  const query = container.resolve(ContainerRegistrationKeys.QUERY);
  const { data } = await query.graph({
    entity: "product_category", fields: ["id", "handle"],
    filters: { handle: STOREFRONT_CATEGORIES.map((category) => category.handle) },
  });
  const existing = new Set((data as { handle?: string }[]).map((row) => row.handle));
  const missing = STOREFRONT_CATEGORIES.filter((category) => !existing.has(category.handle));
  if (missing.length) {
    await createProductCategoriesWorkflow(container).run({ input: { product_categories: missing.map((category) => ({
      ...category, is_active: true, is_internal: false,
    })) } });
  }
  return missing.length;
}

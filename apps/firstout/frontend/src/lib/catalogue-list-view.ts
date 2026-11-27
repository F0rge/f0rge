import { MATERIAL_FAMILY_LABELS, type Category, type Material, type MaterialFamily } from "./catalogue-lists";

/** Where an unmapped category's sales post (the chart's fallback income account). */
export const FALLBACK_SALES_CODE = "4000";

/** "4060 Sales – Dining", or the fallback note for an unmapped category. */
export function salesAccountLabel(category: Pick<Category, "sales_account">): string {
  const account = category.sales_account;
  return account ? `${account.code} ${account.name}` : `Posts to the ${FALLBACK_SALES_CODE} fallback`;
}

/** A category option: "Dining → 4060 Sales – Dining" or "Dining (posts to the 4000 fallback)". */
export function categoryOptionLabel(category: Pick<Category, "name" | "sales_account" | "is_archived">): string {
  const base = category.sales_account
    ? `${category.name} → ${salesAccountLabel(category)}`
    : `${category.name} (posts to the ${FALLBACK_SALES_CODE} fallback)`;
  return category.is_archived ? `${base} · archived` : base;
}

export function subcategoryOptionLabel(sub: Pick<Category, "name" | "is_archived">): string {
  return sub.is_archived ? `${sub.name} · archived` : sub.name;
}

/** Active entries, plus an archived one the record already uses so it still shows. */
function pickable<T extends { id: string; is_archived: boolean }>(items: readonly T[], keepId: string | null | undefined): T[] {
  return items.filter((item) => !item.is_archived || item.id === keepId);
}

export function pickableCategories(categories: readonly Category[], selectedId: string | null | undefined): Category[] {
  return pickable(categories, selectedId);
}

export function pickableSubcategories(
  categories: readonly Category[],
  categoryId: string | null | undefined,
  selectedSubId: string | null | undefined,
): Category[] {
  const parent = categories.find((category) => category.id === categoryId);
  return parent ? pickable(parent.subcategories, selectedSubId) : [];
}

/** The sub-category to keep after the category changes: cleared when it belongs elsewhere. */
export function subcategoryAfterCategoryChange(
  categories: readonly Category[],
  nextCategoryId: string,
  subId: string | null | undefined,
): string {
  const parent = categories.find((category) => category.id === nextCategoryId);
  return subId && parent?.subcategories.some((sub) => sub.id === subId) ? subId : "";
}

export type MaterialGroup = { family: MaterialFamily; label: string; materials: Material[] };

/** Materials grouped by family in the fixed family order; archived ones only when kept. */
export function groupMaterials(materials: readonly Material[], keepIds: readonly string[] = []): MaterialGroup[] {
  const keep = new Set(keepIds);
  const visible = materials.filter((material) => !material.is_archived || keep.has(material.id));
  return (Object.keys(MATERIAL_FAMILY_LABELS) as MaterialFamily[])
    .map((family) => ({
      family,
      label: MATERIAL_FAMILY_LABELS[family],
      materials: visible.filter((material) => material.family === family),
    }))
    .filter((group) => group.materials.length);
}

/** Materials still offered for "Add material": active, not main, not already listed. */
export function addableMaterials(
  materials: readonly Material[],
  mainId: string | null | undefined,
  otherIds: readonly string[],
): Material[] {
  const taken = new Set([mainId, ...otherIds]);
  return materials.filter((material) => !material.is_archived && !taken.has(material.id));
}

export type CategoryRow = { category: Category; parent: Category | null };

/** The Settings tree as table rows: each category, then its sub-categories. */
export function flattenCategoryTree(categories: readonly Category[]): CategoryRow[] {
  return categories.flatMap((category) => [
    { category, parent: null },
    ...category.subcategories.map((sub) => ({ category: sub, parent: category })),
  ]);
}

/** Top-level active categories with no ledger posting entry yet (matched by name, any case). */
export function unmappedCategories(
  categories: readonly Category[],
  mappedNames: readonly string[],
): Category[] {
  const mapped = new Set(mappedNames.map((name) => name.trim().toLowerCase()));
  return categories.filter((category) => !category.is_archived && !mapped.has(category.name.trim().toLowerCase()));
}

/**
 * 422 field errors (`{detail: [{loc: ["body", field], msg}]}`) by field name, so the category,
 * material and colour fields can each show the server's message.
 */
export function fieldErrors(detail: unknown): Record<string, string> {
  const fields: Record<string, string> = {};
  if (!Array.isArray(detail)) return fields;
  for (const issue of detail as { loc?: unknown; msg?: unknown }[]) {
    const field = Array.isArray(issue?.loc) ? issue.loc.find((part, index) => index > 0 && typeof part === "string") : undefined;
    if (typeof field === "string" && !fields[field]) fields[field] = typeof issue.msg === "string" ? issue.msg : "Check this value.";
  }
  return fields;
}

/**
 * What changing a category's shop section does, in plain words, before it is saved:
 * "Puts up to 12 SKUs on the shop in Bedroom." The count is every active SKU in the category;
 * only photographed, unhidden ones actually appear, hence "up to".
 */
export function shopSectionChangeText(
  skuCount: number,
  from: string | null,
  to: string | null,
  label: (slug: string) => string,
): string {
  const skus = `up to ${skuCount} ${skuCount === 1 ? "SKU" : "SKUs"}`;
  if (from === to) return "No change.";
  if (!to) return `Takes ${skus} off the shop.`;
  if (!from) return `Puts ${skus} on the shop in ${label(to)}.`;
  return `Moves ${skus} on the shop from ${label(from)} to ${label(to)}.`;
}

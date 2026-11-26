import { describe, expect, it } from "vitest";

import {
  addableMaterials,
  categoryOptionLabel,
  fieldErrors,
  flattenCategoryTree,
  groupMaterials,
  pickableCategories,
  pickableSubcategories,
  salesAccountLabel,
  subcategoryAfterCategoryChange,
  unmappedCategories,
} from "./catalogue-list-view";
import type { Category, Material } from "./catalogue-lists";

function category(id: string, name: string, extra: Partial<Category> = {}): Category {
  return {
    id, name, parent_id: null, is_archived: false, shop_category: null, sales_account: null,
    sku_count: 0, subcategories: [], ...extra,
  };
}

const chairs = category("chairs", "Chairs", { parent_id: "dining" });
const oldBenches = category("benches", "Benches", { parent_id: "dining", is_archived: true });
const dining = category("dining", "Dining", {
  sales_account: { code: "4060", name: "Sales – Dining" },
  subcategories: [chairs, oldBenches],
});
const rugs = category("rugs", "Rugs");
const retired = category("retired", "Retired", { is_archived: true });
const tree = [dining, rugs, retired];

describe("category labels", () => {
  it("names the sales account or flags the fallback", () => {
    expect(categoryOptionLabel(dining)).toBe("Dining → 4060 Sales – Dining");
    expect(categoryOptionLabel(rugs)).toBe("Rugs (posts to the 4000 fallback)");
    expect(categoryOptionLabel(retired)).toBe("Retired (posts to the 4000 fallback) · archived");
    expect(salesAccountLabel(rugs)).toBe("Posts to the 4000 fallback");
  });
});

describe("pickers", () => {
  it("offers active entries and keeps an archived one already chosen", () => {
    expect(pickableCategories(tree, null).map((c) => c.id)).toEqual(["dining", "rugs"]);
    expect(pickableCategories(tree, "retired").map((c) => c.id)).toEqual(["dining", "rugs", "retired"]);
    expect(pickableSubcategories(tree, "dining", null).map((c) => c.id)).toEqual(["chairs"]);
    expect(pickableSubcategories(tree, "dining", "benches").map((c) => c.id)).toEqual(["chairs", "benches"]);
    expect(pickableSubcategories(tree, "", null)).toEqual([]);
  });

  it("clears a sub-category that does not belong to the new category", () => {
    expect(subcategoryAfterCategoryChange(tree, "rugs", "chairs")).toBe("");
    expect(subcategoryAfterCategoryChange(tree, "dining", "chairs")).toBe("chairs");
  });
});

function material(id: string, family: Material["family"], is_archived = false): Material {
  return { id, name: id, family, is_archived, sku_count: 0 };
}

describe("materials", () => {
  const materials = [material("oak", "wood"), material("linen", "fabric"), material("old", "wood", true), material("brass", "metal")];

  it("groups by family in the fixed order, archived only when kept", () => {
    expect(groupMaterials(materials).map((g) => [g.family, g.materials.map((m) => m.id)])).toEqual([
      ["fabric", ["linen"]], ["wood", ["oak"]], ["metal", ["brass"]],
    ]);
    expect(groupMaterials(materials, ["old"])[1].materials.map((m) => m.id)).toEqual(["oak", "old"]);
  });

  it("never offers the main material, a listed one or an archived one", () => {
    expect(addableMaterials(materials, "oak", ["linen"]).map((m) => m.id)).toEqual(["brass"]);
  });
});

describe("settings tree", () => {
  it("lists each category followed by its sub-categories", () => {
    expect(flattenCategoryTree([dining, rugs]).map((row) => [row.category.id, row.parent?.id ?? null])).toEqual([
      ["dining", null], ["chairs", "dining"], ["benches", "dining"], ["rugs", null],
    ]);
  });

  it("finds active categories with no posting entry, ignoring case", () => {
    expect(unmappedCategories(tree, ["DINING "]).map((c) => c.id)).toEqual(["rugs"]);
  });
});

describe("fieldErrors", () => {
  it("keys the server's 422 messages by field", () => {
    expect(fieldErrors([
      { loc: ["body", "subcategory_id"], msg: "'Y' is not a sub-category of X" },
      { loc: ["body", "other_material_ids", 0], msg: "Material not found" },
    ])).toEqual({ subcategory_id: "'Y' is not a sub-category of X", other_material_ids: "Material not found" });
    expect(fieldErrors("Category not found")).toEqual({});
  });
});

import type { MedusaContainer } from "@medusajs/framework/types";
import { createProductCategoriesWorkflow } from "@medusajs/medusa/core-flows";
import {
  CATALOGUE_COLLECTION_HANDLE, CATALOGUE_COLLECTION_TITLE, LEGACY_CATALOGUE_COLLECTION_HANDLE, STOREFRONT_CATEGORIES,
  collectionEnsurePlan, ensureStorefrontCategories,
} from "./catalogue-collections";

jest.mock("@medusajs/medusa/core-flows", () => ({ createProductCategoriesWorkflow: jest.fn() }));

test("the bootstrap creates the four public categories once and never edits staff changes", async () => {
  type Category = { id: string; handle: string; name: string; is_active: boolean; is_internal: boolean };
  const categories: Category[] = [];
  const run = jest.fn(async ({ input }: { input: { product_categories: Omit<Category, "id">[] } }) => {
    categories.push(...input.product_categories.map((category, index) => ({ ...category, id: `pcat_${categories.length + index}` })));
    return { result: [] };
  });
  (createProductCategoriesWorkflow as unknown as jest.Mock).mockReturnValue({ run });
  const graph = jest.fn(async ({ entity, filters }: { entity: string; filters: { handle: string[] } }) => {
    if (entity !== "product_category") throw new Error(`unexpected entity ${entity}`);
    return { data: categories.filter((category) => filters.handle.includes(category.handle)) };
  });
  const container = { resolve: () => ({ graph }) } as unknown as MedusaContainer;

  expect(await ensureStorefrontCategories(container)).toBe(4);
  expect(categories.map(({ handle, name, is_active, is_internal }) => ({ handle, name, is_active, is_internal }))).toEqual([
    { handle: "sofas-armchairs", name: "Sofas & Armchairs", is_active: true, is_internal: false },
    { handle: "dining-room", name: "Dining Room", is_active: true, is_internal: false },
    { handle: "bedroom", name: "Bedroom", is_active: true, is_internal: false },
    { handle: "coffee-console-tables", name: "Coffee & Console Tables", is_active: true, is_internal: false },
  ]);

  // Staff renamed one and hid another in Admin; a release re-runs the bootstrap.
  categories[0].name = "Lounge";
  categories[1].is_active = false;
  expect(await ensureStorefrontCategories(container)).toBe(0);
  expect(run).toHaveBeenCalledTimes(1);
  expect(categories).toHaveLength(STOREFRONT_CATEGORIES.length);
  expect(categories[0].name).toBe("Lounge");
  expect(categories[1].is_active).toBe(false);
});

test("On Sale renames the old in-stock collection in place", () => {
  expect(CATALOGUE_COLLECTION_HANDLE).toBe("on-sale");
  expect(CATALOGUE_COLLECTION_TITLE).toBe("On Sale");
  expect(LEGACY_CATALOGUE_COLLECTION_HANDLE).toBe("in-stock");
  const legacy = { id: "pcol_sale", handle: "in-stock", title: "In stock" };
  expect(collectionEnsurePlan([legacy], CATALOGUE_COLLECTION_HANDLE, CATALOGUE_COLLECTION_TITLE, LEGACY_CATALOGUE_COLLECTION_HANDLE))
    .toEqual({ action: "rename", id: "pcol_sale" });
  expect(collectionEnsurePlan(
    [{ id: "pcol_sale", handle: "on-sale", title: "On Sale" }, legacy],
    CATALOGUE_COLLECTION_HANDLE, CATALOGUE_COLLECTION_TITLE, LEGACY_CATALOGUE_COLLECTION_HANDLE,
  )).toEqual({ action: "keep", id: "pcol_sale" });
  expect(collectionEnsurePlan(
    [{ id: "pcol_sale", handle: "on-sale", title: "Sale" }],
    CATALOGUE_COLLECTION_HANDLE, CATALOGUE_COLLECTION_TITLE,
  )).toEqual({ action: "retitle", id: "pcol_sale" });
  expect(collectionEnsurePlan([], CATALOGUE_COLLECTION_HANDLE, CATALOGUE_COLLECTION_TITLE)).toEqual({ action: "create" });
});

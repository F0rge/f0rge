import type { components } from "./generated/api-schema";
import { apiFetch } from "./api";

type Schema = components["schemas"];

/** Managed categories (two levels), materials, and the per-SKU endpoints built on them. */
export type Category = Schema["CategoryResponse"];
export type CategoryTree = Schema["CategoryTree"];
export type CategoryCreate = Schema["CategoryCreate"];
export type CategoryUpdate = Schema["CategoryUpdate"];
export type ShopSection = Schema["ShopSection"];
export type Material = Schema["MaterialResponse"];
export type MaterialCreate = Schema["MaterialCreate"];
export type MaterialUpdate = Schema["MaterialUpdate"];
export type MaterialFamily = Material["family"];
export type ListLifecycle = "active" | "archived" | "all";

export type SkuOverview = Schema["SkuOverviewResponse"];
export type SkuSupplierPrice = Schema["SkuSupplierPriceResponse"];
export type SkuSupplierPricesReplace = Schema["SkuSupplierPricesReplace"];

/** Display order and labels for material families; the API sends them lower case. */
export const MATERIAL_FAMILY_LABELS: Record<MaterialFamily, string> = {
  fabric: "Fabric",
  leather: "Leather",
  wood: "Wood",
  stone: "Stone",
  metal: "Metal",
  glass: "Glass",
  woven: "Woven",
  other: "Other",
};

export const catalogueListKeys = {
  categories: (lifecycle: ListLifecycle = "active") => ["categories", lifecycle] as const,
  materials: (lifecycle: ListLifecycle = "active") => ["materials", lifecycle] as const,
  skuOverview: (id: string) => ["sku-overview", id] as const,
  skuSupplierPrices: (id: string) => ["sku-supplier-prices", id] as const,
};

const json = (method: string, payload: unknown): RequestInit => ({ method, body: JSON.stringify(payload) });

export function listCategories(lifecycle: ListLifecycle = "active"): Promise<CategoryTree> {
  return apiFetch<CategoryTree>(`/categories?lifecycle=${lifecycle}`);
}
export function createCategory(payload: CategoryCreate): Promise<Category> {
  return apiFetch<Category>("/categories", json("POST", payload));
}
export function updateCategory(id: string, payload: CategoryUpdate): Promise<Category> {
  return apiFetch<Category>(`/categories/${id}`, json("PATCH", payload));
}

export function listMaterials(lifecycle: ListLifecycle = "active"): Promise<Material[]> {
  return apiFetch<Material[]>(`/materials?lifecycle=${lifecycle}`);
}
export function createMaterial(payload: MaterialCreate): Promise<Material> {
  return apiFetch<Material>("/materials", json("POST", payload));
}
export function updateMaterial(id: string, payload: MaterialUpdate): Promise<Material> {
  return apiFetch<Material>(`/materials/${id}`, json("PATCH", payload));
}

export function getSkuOverview(id: string, signal?: AbortSignal): Promise<SkuOverview> {
  return apiFetch<SkuOverview>(`/skus/${id}/overview`, { signal });
}
export function listSkuSupplierPrices(id: string): Promise<SkuSupplierPrice[]> {
  return apiFetch<SkuSupplierPrice[]>(`/skus/${id}/supplier-prices`);
}
export function replaceSkuSupplierPrices(id: string, payload: SkuSupplierPricesReplace): Promise<SkuSupplierPrice[]> {
  return apiFetch<SkuSupplierPrice[]>(`/skus/${id}/supplier-prices`, json("PUT", payload));
}

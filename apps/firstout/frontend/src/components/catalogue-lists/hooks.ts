"use client";

import { useQuery } from "@tanstack/react-query";

import { catalogueListKeys, listCategories, listMaterials, type ListLifecycle } from "@/lib/catalogue-lists";

/**
 * The managed category tree (`data.categories`, `data.shop_sections`). Pickers use the default
 * "all" so an archived category already on a record still has its name; they hide archived
 * options themselves.
 */
export function useCategories(lifecycle: ListLifecycle = "all") {
  return useQuery({ queryKey: catalogueListKeys.categories(lifecycle), queryFn: () => listCategories(lifecycle) });
}

/** The managed materials; "all" by default for the same reason as `useCategories`. */
export function useMaterials(lifecycle: ListLifecycle = "all") {
  return useQuery({ queryKey: catalogueListKeys.materials(lifecycle), queryFn: () => listMaterials(lifecycle) });
}

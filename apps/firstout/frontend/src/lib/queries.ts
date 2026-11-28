import { queryOptions, useQueries } from "@tanstack/react-query";

import {
  getSettings,
  listCustomers,
  listInventory,
  listLocations,
  listPicks,
  listPriceLists,
  listSalesStaffOptions,
  listSkus,
  type CustomerCrm,
  type PriceList,
  type Sku,
} from "@/lib/api";

/**
 * Query keys for reference data shared across pages. Each key is a prefix: a page that
 * filters (for example archived customers) appends to it, so invalidating the base key
 * after a write refreshes every variant.
 */
export const queryKeys = {
  skus: ["skus"],
  customers: ["customers"],
  priceLists: ["price-lists"],
  settings: ["settings"],
  locations: ["locations"],
  salesStaffOptions: ["sales-staff", "options"],
  inventory: ["inventory"],
  tillReservations: ["till-reservations"],
  picks: ["picks"],
} as const;

// Reference data changes rarely; pages share one copy for this long.
const REFERENCE_STALE_MS = 30_000;

/** Pass to `useQuery`, `useQueries` or `queryClient.fetchQuery`. */
export const referenceQueries = {
  skus: queryOptions({ queryKey: queryKeys.skus, queryFn: () => listSkus(), staleTime: REFERENCE_STALE_MS }),
  customers: queryOptions({ queryKey: queryKeys.customers, queryFn: () => listCustomers(), staleTime: REFERENCE_STALE_MS }),
  priceLists: queryOptions({ queryKey: queryKeys.priceLists, queryFn: listPriceLists, staleTime: REFERENCE_STALE_MS }),
  settings: queryOptions({ queryKey: queryKeys.settings, queryFn: getSettings, staleTime: REFERENCE_STALE_MS }),
  locations: queryOptions({ queryKey: queryKeys.locations, queryFn: listLocations, staleTime: REFERENCE_STALE_MS }),
  salesStaffOptions: queryOptions({ queryKey: queryKeys.salesStaffOptions, queryFn: listSalesStaffOptions, staleTime: REFERENCE_STALE_MS }),
};

/** Stock and till picks: every sale changes them, so they are never fresh for long. */
export const stockQueries = {
  inventory: queryOptions({ queryKey: queryKeys.inventory, queryFn: () => listInventory() }),
  tillPicks: queryOptions({ queryKey: [...queryKeys.picks, "till"], queryFn: () => listPicks("till") }),
};

type Result<T> = { data?: T; error: Error | null };

// Module-level so TanStack keeps the combined object stable between renders.
export function combineSaleReference([skus, customers, priceLists]: [
  Result<Sku[]>, Result<CustomerCrm[]>, Result<PriceList[]>,
]) {
  return {
    error: skus.error ?? customers.error ?? priceLists.error,
    data: skus.data && customers.data && priceLists.data
      ? { skus: skus.data, customers: customers.data, priceLists: priceLists.data }
      : undefined,
  };
}

/**
 * What a sale's finder offers: catalogue, customers, and the price lists that decide
 * which SKUs the server can price (`mayBePriced`). The invoice and quote editors load
 * this one copy. `data` is undefined until all three arrive; `error` is the first failure.
 */
export function useSaleReference() {
  return useQueries({
    queries: [referenceQueries.skus, referenceQueries.customers, referenceQueries.priceLists],
    combine: combineSaleReference,
  });
}

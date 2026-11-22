import { queryOptions, useQueries } from "@tanstack/react-query";

import {
  getSettings,
  listCustomers,
  listLocations,
  listPriceLists,
  listSalesStaffOptions,
  listSkus,
  type AppSettings,
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

/** VAT rate shown when settings carry none. */
export const DEFAULT_VAT_PERCENT = "15";

type Result<T> = { data?: T; error: Error | null };

// Module-level so TanStack keeps the combined object stable between renders.
export function combineSaleReference([skus, customers, priceLists, settings]: [
  Result<Sku[]>, Result<CustomerCrm[]>, Result<PriceList[]>, Result<AppSettings>,
]) {
  return {
    error: skus.error ?? customers.error ?? priceLists.error ?? settings.error,
    data: skus.data && customers.data && priceLists.data && settings.data
      ? {
          skus: skus.data,
          customers: customers.data,
          priceLists: priceLists.data,
          settings: settings.data,
          vatPercent: settings.data.vat_percent ?? DEFAULT_VAT_PERCENT,
        }
      : undefined,
  };
}

/**
 * What a sale is priced against: catalogue, customers, price lists and settings. The
 * invoice and quote editors load this one copy; the till still has its own loader.
 * `data` is undefined until all four arrive; `error` is the first failure.
 */
export function useSaleReference() {
  return useQueries({
    queries: [referenceQueries.skus, referenceQueries.customers, referenceQueries.priceLists, referenceQueries.settings],
    combine: combineSaleReference,
  });
}

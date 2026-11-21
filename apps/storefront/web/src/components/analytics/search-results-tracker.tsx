"use client";

import { useEffect } from "react";
import type { SearchAvailability, SearchSortOrder } from "@/lib/analytics/events";
import { createSearchVisitGuard } from "@/lib/analytics/search-visit";
import { useStorefrontAnalytics } from "./analytics-provider";

const searchVisit = createSearchVisitGuard();

export function SearchResultsTracker({ queryPresent, categoryId, availability, priceFilterActive, sortOrder, resultCount }: {
  queryPresent: boolean;
  categoryId?: string;
  availability: SearchAvailability;
  priceFilterActive: boolean;
  sortOrder: SearchSortOrder;
  resultCount: number;
}) {
  const { choice, capture } = useStorefrontAnalytics();

  useEffect(() => {
    const key = [queryPresent, categoryId || "", availability, priceFilterActive, sortOrder, resultCount].join(":");
    if (searchVisit.shouldCapture(choice === "accepted", key)) {
      capture({
        name: "storefront_search_results_viewed",
        properties: { query_present: queryPresent, category_id: categoryId, availability, price_filter_active: priceFilterActive, sort_order: sortOrder, result_count: resultCount },
      });
    }
    return () => searchVisit.release();
  }, [availability, capture, categoryId, choice, priceFilterActive, queryPresent, resultCount, sortOrder]);

  return null;
}

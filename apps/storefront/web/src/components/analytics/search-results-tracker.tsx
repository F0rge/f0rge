"use client";

import { useEffect } from "react";
import type { SearchSortOrder } from "@/lib/analytics/events";
import { createSearchVisitGuard } from "@/lib/analytics/search-visit";
import { useStorefrontAnalytics } from "./analytics-provider";

const searchVisit = createSearchVisitGuard();

export function SearchResultsTracker({ queryPresent, categoryId, collectionId, availability, priceFilterActive, sortOrder, resultCount }: {
  queryPresent: boolean;
  categoryId?: string;
  collectionId?: string;
  availability: "all" | "in_stock";
  priceFilterActive: boolean;
  sortOrder: SearchSortOrder;
  resultCount: number;
}) {
  const { choice, capture } = useStorefrontAnalytics();

  useEffect(() => {
    const key = [queryPresent, categoryId || "", collectionId || "", availability, priceFilterActive, sortOrder, resultCount].join(":");
    if (searchVisit.shouldCapture(choice === "accepted", key)) {
      capture({
        name: "storefront_search_results_viewed",
        properties: { query_present: queryPresent, category_id: categoryId, collection_id: collectionId, availability, price_filter_active: priceFilterActive, sort_order: sortOrder, result_count: resultCount },
      });
    }
    return () => searchVisit.release();
  }, [availability, capture, categoryId, choice, collectionId, priceFilterActive, queryPresent, resultCount, sortOrder]);

  return null;
}

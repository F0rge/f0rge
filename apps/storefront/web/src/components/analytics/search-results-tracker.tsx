"use client";

import { useEffect } from "react";
import type { SearchSortOrder } from "@/lib/analytics/events";
import { useStorefrontAnalytics } from "./analytics-provider";

const lastSearchKey = { current: "" };

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
    if (choice !== "accepted") {
      lastSearchKey.current = "";
      return;
    }
    const key = [queryPresent, categoryId || "", collectionId || "", availability, priceFilterActive, sortOrder, resultCount].join(":");
    if (lastSearchKey.current === key) return;
    lastSearchKey.current = key;
    capture({
      name: "storefront_search_results_viewed",
      properties: { query_present: queryPresent, category_id: categoryId, collection_id: collectionId, availability, price_filter_active: priceFilterActive, sort_order: sortOrder, result_count: resultCount },
    });
  }, [availability, capture, categoryId, choice, collectionId, priceFilterActive, queryPresent, resultCount, sortOrder]);

  return null;
}

import { useMemo, useState } from "react";

export const CLIENT_PAGE_SIZES = [10, 25, 50] as const;

type PaginationChange = {
  page: number;
  pageSize: number;
};

export function useClientPagination<T>(items: T[], resetKey: string | number) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<(typeof CLIENT_PAGE_SIZES)[number]>(10);
  const [seenKey, setSeenKey] = useState(resetKey);

  if (seenKey !== resetKey) {
    setSeenKey(resetKey);
    setPage(1);
  }

  const pagedItems = useMemo(() => {
    const start = (page - 1) * pageSize;
    return items.slice(start, start + pageSize);
  }, [items, page, pageSize]);

  return {
    page,
    pageSize,
    pagedItems,
    totalItems: items.length,
    onPaginationChange: ({ page: nextPage, pageSize: nextSize }: PaginationChange) => {
      setPage(nextPage);
      setPageSize(nextSize as (typeof CLIENT_PAGE_SIZES)[number]);
    },
  };
}

"use client";

import {
  InlineNotification,
  Pagination,
  Search,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
} from "@carbon/react";
import { useCallback, useEffect, useState, type ReactNode } from "react";

import { PAGE_SIZES, type ListParams, type Page } from "@/lib/api";

export type RecordsColumn<T> = {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
};

type Props<T> = {
  title: string;
  description?: string;
  columns: RecordsColumn<T>[];
  load: (params: ListParams) => Promise<Page<T>>;
  rowId: (row: T, index: number) => string;
  searchPlaceholder?: string;
  emptyText?: string;
};

/** Server-paged read-only Carbon table with a search box. */
export function RecordsTable<T>({
  title,
  description,
  columns,
  load,
  rowId,
  searchPlaceholder = "Search",
  emptyText = "Nothing to show.",
}: Props<T>) {
  const [rows, setRows] = useState<T[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(PAGE_SIZES[1]);
  const [query, setQuery] = useState("");
  const [debounced, setDebounced] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebounced(query);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await load({
        limit: pageSize,
        offset: (page - 1) * pageSize,
        q: debounced || undefined,
      });
      setRows(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load.");
    } finally {
      setLoading(false);
    }
  }, [load, page, pageSize, debounced]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <Stack gap={4}>
      {error ? (
        <InlineNotification kind="error" title="Error" subtitle={error} lowContrast hideCloseButton />
      ) : null}
      <Search
        labelText={searchPlaceholder}
        placeholder={searchPlaceholder}
        size="md"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      <TableContainer title={title} description={description}>
        <Table size="sm">
          <TableHead>
            <TableRow>
              {columns.map((column) => (
                <TableHeader key={column.key}>{column.header}</TableHeader>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={columns.length}>{loading ? "Loading…" : emptyText}</TableCell>
              </TableRow>
            ) : (
              rows.map((row, index) => (
                <TableRow key={rowId(row, index)}>
                  {columns.map((column) => (
                    <TableCell key={column.key}>{column.render(row)}</TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
      <Pagination
        page={page}
        pageSize={pageSize}
        pageSizes={[...PAGE_SIZES]}
        totalItems={total}
        onChange={({ page: nextPage, pageSize: nextSize }) => {
          setPage(nextPage);
          setPageSize(nextSize);
        }}
      />
    </Stack>
  );
}

"use client";

import {
  ClickableTile,
  Layer,
  Search,
  Stack,
  StructuredListBody,
  StructuredListCell,
  StructuredListHead,
  StructuredListRow,
  StructuredListWrapper,
  Tile,
} from "@carbon/react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { searchAll, type SearchResponse } from "@/lib/api";

type HeaderSearchProps = {
  className?: string;
};

export function HeaderSearch({ className }: HeaderSearchProps) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runSearch = useCallback(async (term: string) => {
    const trimmed = term.trim();
    if (!trimmed) {
      setResults(null);
      setOpen(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await searchAll(trimmed);
      setResults(response);
      setOpen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
      setResults(null);
      setOpen(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      void runSearch(query);
    }, 250);
    return () => window.clearTimeout(handle);
  }, [query, runSearch]);

  const hasHits =
    results &&
    (results.skus.length > 0 ||
      results.purchase_orders.length > 0 ||
      results.invoices.length > 0);

  return (
    <div className={className ?? "vellano-header-search"}>
      <Search
        size="sm"
        labelText="Search SKUs, POs, invoices"
        placeholder="Search barcode, PO, invoice…"
        closeButtonLabelText="Clear search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        onClear={() => {
          setQuery("");
          setResults(null);
          setOpen(false);
        }}
        onFocus={() => {
          if (query.trim()) {
            setOpen(true);
          }
        }}
      />
      {open && query.trim() ? (
        <Layer className="vellano-header-search__panel">
          {loading ? <Tile className="vellano-header-search__empty">Searching…</Tile> : null}
          {error ? (
            <Tile className="vellano-header-search__empty">{error}</Tile>
          ) : null}
          {!loading && !error && results && !hasHits ? (
            <Tile className="vellano-header-search__empty">No matches for “{results.q}”.</Tile>
          ) : null}
          {!loading && !error && results && hasHits ? (
            <Stack gap={4}>
              {results.skus.length > 0 ? (
                <StructuredListWrapper aria-label="SKU results">
                  <StructuredListHead>
                    <StructuredListRow head>
                      <StructuredListCell head>SKUs</StructuredListCell>
                    </StructuredListRow>
                  </StructuredListHead>
                  <StructuredListBody>
                    {results.skus.map((sku) => (
                      <StructuredListRow key={sku.id}>
                        <StructuredListCell>
                          <ClickableTile
                            onClick={() => {
                              setOpen(false);
                              router.push(`/catalogue?barcode=${encodeURIComponent(sku.our_barcode)}`);
                            }}
                          >
                            {sku.our_barcode} — {sku.name} ({sku.our_ref})
                          </ClickableTile>
                        </StructuredListCell>
                      </StructuredListRow>
                    ))}
                  </StructuredListBody>
                </StructuredListWrapper>
              ) : null}
              {results.purchase_orders.length > 0 ? (
                <StructuredListWrapper aria-label="Purchase order results">
                  <StructuredListHead>
                    <StructuredListRow head>
                      <StructuredListCell head>Purchase orders</StructuredListCell>
                    </StructuredListRow>
                  </StructuredListHead>
                  <StructuredListBody>
                    {results.purchase_orders.map((po) => (
                      <StructuredListRow key={po.id}>
                        <StructuredListCell>
                          <ClickableTile
                            onClick={() => {
                              setOpen(false);
                              router.push(`/purchase-orders/${po.id}`);
                            }}
                          >
                            {po.po_number} — {po.supplier_name} ({po.status})
                          </ClickableTile>
                        </StructuredListCell>
                      </StructuredListRow>
                    ))}
                  </StructuredListBody>
                </StructuredListWrapper>
              ) : null}
              {results.invoices.length > 0 ? (
                <StructuredListWrapper aria-label="Invoice results">
                  <StructuredListHead>
                    <StructuredListRow head>
                      <StructuredListCell head>Invoices</StructuredListCell>
                    </StructuredListRow>
                  </StructuredListHead>
                  <StructuredListBody>
                    {results.invoices.map((invoice) => (
                      <StructuredListRow key={invoice.id}>
                        <StructuredListCell>
                          <ClickableTile
                            onClick={() => {
                              setOpen(false);
                              router.push(`/invoices/${invoice.id}`);
                            }}
                          >
                            {invoice.invoice_number} — {invoice.customer_name}
                          </ClickableTile>
                        </StructuredListCell>
                      </StructuredListRow>
                    ))}
                  </StructuredListBody>
                </StructuredListWrapper>
              ) : null}
            </Stack>
          ) : null}
        </Layer>
      ) : null}
    </div>
  );
}

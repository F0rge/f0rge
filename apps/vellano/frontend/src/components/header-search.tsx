"use client";

import { Search, Theme } from "@carbon/react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { searchAll, type SearchResponse } from "@/lib/api";

type HeaderSearchProps = {
  className?: string;
};

export function HeaderSearch({ className }: HeaderSearchProps) {
  const router = useRouter();
  const rootRef = useRef<HTMLDivElement>(null);
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

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function handleKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKey);
    };
  }, []);

  const hasHits =
    results &&
    (results.skus.length > 0 ||
      results.purchase_orders.length > 0 ||
      results.invoices.length > 0);

  function goTo(href: string) {
    setOpen(false);
    router.push(href);
  }

  return (
    <div ref={rootRef} className={className ?? "vellano-header-search"}>
      <Search
        size="sm"
        labelText="Search SKUs, POs, invoices"
        placeholder="Search..."
        closeButtonLabelText="Clear search"
        value={query}
        autoComplete="off"
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
        <Theme theme="g10" className="vellano-header-search__panel">
          {loading ? <div className="vellano-header-search__empty">Searching…</div> : null}
          {error ? <div className="vellano-header-search__empty">{error}</div> : null}
          {!loading && !error && results && !hasHits ? (
            <div className="vellano-header-search__empty">No matches for “{results.q}”.</div>
          ) : null}
          {!loading && !error && results && hasHits ? (
            <>
              {results.skus.length > 0 ? (
                <section>
                  <p className="vellano-header-search__group">SKUs</p>
                  <ul className="vellano-header-search__hits">
                    {results.skus.map((sku) => (
                      <li key={sku.id}>
                        <button
                          type="button"
                          className="vellano-header-search__hit"
                          onClick={() =>
                            goTo(`/catalogue?barcode=${encodeURIComponent(sku.our_barcode)}`)
                          }
                        >
                          {sku.our_barcode} — {sku.name} ({sku.our_ref})
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
              {results.purchase_orders.length > 0 ? (
                <section>
                  <p className="vellano-header-search__group">Purchase orders</p>
                  <ul className="vellano-header-search__hits">
                    {results.purchase_orders.map((po) => (
                      <li key={po.id}>
                        <button
                          type="button"
                          className="vellano-header-search__hit"
                          onClick={() => goTo(`/purchase-orders/${po.id}`)}
                        >
                          {po.po_number} — {po.supplier_name} ({po.status})
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
              {results.invoices.length > 0 ? (
                <section>
                  <p className="vellano-header-search__group">Invoices</p>
                  <ul className="vellano-header-search__hits">
                    {results.invoices.map((invoice) => (
                      <li key={invoice.id}>
                        <button
                          type="button"
                          className="vellano-header-search__hit"
                          onClick={() => goTo(`/invoices/${invoice.id}`)}
                        >
                          {invoice.invoice_number} — {invoice.customer_name}
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              ) : null}
            </>
          ) : null}
        </Theme>
      ) : null}
    </div>
  );
}

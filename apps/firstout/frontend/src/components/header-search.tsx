"use client";

import { Search, Theme } from "@carbon/react";
import Link from "next/link";
import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";

import { searchAdminDestinations } from "@/lib/admin-navigation";
import { searchAll, type AuthUser, type SearchResponse } from "@/lib/api";

type HeaderSearchProps = {
  className?: string;
  administrationUser?: AuthUser | null;
};

type RecordSearch = {
  term: string;
  results?: SearchResponse;
  error?: string;
};

export function HeaderSearch({ className, administrationUser }: HeaderSearchProps) {
  const input = useRef<HTMLInputElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const panelId = useId();
  const [query, setQuery] = useState("");
  const [recordSearch, setRecordSearch] = useState<RecordSearch>();
  const [open, setOpen] = useState(false);
  const term = query.trim();
  const currentSearch = recordSearch?.term === term ? recordSearch : undefined;
  const results = currentSearch?.results;
  const panelOpen = open && !!term;

  useEffect(() => {
    if (!term) return;

    const request = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const results = await searchAll(term, request.signal);
        if (!request.signal.aborted) setRecordSearch({ term, results });
      } catch (reason) {
        if (!request.signal.aborted) {
          setRecordSearch({ term, error: reason instanceof Error ? reason.message : "Search failed." });
        }
      }
    }, 250);

    return () => {
      window.clearTimeout(timer);
      request.abort();
    };
  }, [term]);

  const groups = [
    { label: "Administration", hits: searchAdminDestinations(term, administrationUser) },
    { label: "SKUs", hits: results?.skus.map((sku) => ({
      href: "/catalogue/" + sku.id, label: sku.our_barcode + " — " + sku.name + " (" + sku.our_ref + ")",
    })) ?? [] },
    { label: "Purchase orders", hits: results?.purchase_orders.map((order) => ({
      href: "/purchase-orders/" + order.id, label: order.po_number + " — " + order.supplier_name + " (" + order.status + ")",
    })) ?? [] },
    { label: "Invoices", hits: results?.invoices.map((invoice) => ({
      href: "/invoices/" + invoice.id, label: invoice.invoice_number + " — " + invoice.customer_name,
    })) ?? [] },
  ].filter(({ hits }) => hits.length > 0);

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape" && panelOpen) {
      event.preventDefault();
      event.stopPropagation();
      input.current?.focus();
      setOpen(false);
      return;
    }

    if (!term || (event.key !== "ArrowDown" && event.key !== "ArrowUp" && event.key !== "Enter")) return;
    const fromSearch = event.target === input.current;
    if (event.key === "Enter" && !fromSearch) return;

    event.preventDefault();
    if (!panelOpen) {
      setOpen(true);
      return;
    }
    const links = Array.from(panel.current?.querySelectorAll<HTMLAnchorElement>("a[href]") ?? []);
    if (event.key === "Enter") {
      links[0]?.click();
      return;
    }
    const selected = links.findIndex((link) => link === event.target);
    if (event.key === "ArrowDown") {
      links[selected + 1]?.focus();
    } else if (selected === 0) {
      input.current?.focus();
    } else {
      links[selected < 0 ? links.length - 1 : selected - 1]?.focus();
    }
  }

  return (
    <div
      role="search"
      aria-label="Firstout"
      className={className ?? "firstout-header-search"}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
      }}
      onKeyDown={handleKeyDown}
    >
      <Search
        ref={input}
        size="sm"
        labelText={administrationUser ? "Search Administration and records" : "Search SKUs, POs, invoices"}
        placeholder="Search…"
        closeButtonLabelText="Clear search"
        value={query}
        aria-controls={panelOpen ? panelId : undefined}
        autoComplete="off"
        onChange={(event) => { setQuery(event.target.value); setOpen(true); }}
        onClear={() => { setQuery(""); setOpen(false); }}
        onFocus={() => setOpen(true)}
      />
      {panelOpen && (
        <Theme theme="g10">
          <div className="firstout-header-search__panel" id={panelId} ref={panel}>
            {groups.map(({ label, hits }) => (
              <section aria-label={label} key={label}>
                <p className="firstout-header-search__group">{label}</p>
                <ul className="firstout-header-search__hits">
                  {hits.map((hit) => (
                    <li key={hit.href}>
                      <Link href={hit.href} className="firstout-header-search__hit" onNavigate={() => {
                        setOpen(false);
                        setQuery("");
                      }}>{hit.label}</Link>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
            <div role="status">
              {!currentSearch && !groups.length && <p className="firstout-header-search__empty">Searching…</p>}
              {currentSearch?.error && <p className="firstout-header-search__empty">{currentSearch.error}</p>}
              {results && !groups.length && <p className="firstout-header-search__empty">No matches for “{term}”.</p>}
            </div>
          </div>
        </Theme>
      )}
    </div>
  );
}

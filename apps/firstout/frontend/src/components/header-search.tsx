"use client";

import { Search, SkeletonText, Tag, Theme } from "@carbon/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState, type KeyboardEvent, type MouseEvent } from "react";

import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { SkuThumb } from "@/components/sku-panel/sku-thumb";
import { useSkuPanel } from "@/components/sku-panel/provider";
import { searchAdminDestinations } from "@/lib/admin-navigation";
import { formatZarAmount, searchAll, type AuthUser } from "@/lib/api";
import { catalogueListKeys, getSkuOverview, type SkuOverview } from "@/lib/catalogue-lists";
import { moveHighlight, searchGroups, skuIds, type SearchOption } from "@/lib/header-search";
import { keysBelongToTarget } from "@/lib/sku-panel";
import { SKU_PRICE_TIERS } from "@/lib/sku-price-form";
import { customersSee, formatCount, nextArrivalText } from "@/lib/sku-summary";

type HeaderSearchProps = {
  className?: string;
  administrationUser?: AuthUser | null;
};

const PREVIEW_DELAY_MS = 150;

function plainClick(event: MouseEvent) {
  return event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;
}

function SkuPreview({ data }: { data: SkuOverview }) {
  const { sku, stock } = data;
  return (
    <>
      <div className="firstout-header-search__preview-head">
        <SkuThumb sku={sku} className="firstout-header-search__preview-thumb" />
        <div>
          <p className="firstout-header-search__preview-name">{sku.name}</p>
          <code>{sku.our_ref}</code>
        </div>
      </div>
      <section aria-label="Stock">
        <p className="firstout-header-search__preview-label">Stock</p>
        {data.is_kit ? (
          <dl><div><dt>Built from parts</dt><dd>{formatCount(stock.available)} available</dd></div></dl>
        ) : (
          <dl>
            {stock.locations.map((location) => (
              <div key={location.location_id}><dt>{location.location_name}</dt><dd>{formatCount(location.on_hand)}</dd></div>
            ))}
            <div><dt>Held</dt><dd>{formatCount(stock.held)}</dd></div>
            <div><dt>Available</dt><dd><strong>{formatCount(stock.available)}</strong></dd></div>
            <div><dt>On order</dt><dd>{formatCount(stock.on_order)}</dd></div>
          </dl>
        )}
      </section>
      <section aria-label="Pricing">
        <p className="firstout-header-search__preview-label">Pricing</p>
        <dl>
          {SKU_PRICE_TIERS.map((tier) => (
            <div key={tier.field}><dt>{tier.label}</dt><dd>{formatZarAmount(sku[tier.field])}</dd></div>
          ))}
        </dl>
        {(sku.sell_multiple > 1 || sku.min_sell_qty > sku.sell_multiple) && (
          <p className="firstout-header-search__preview-help">{customersSee(sku.retail_inc_vat, sku.sell_multiple, sku.min_sell_qty)}</p>
        )}
      </section>
      {(sku.colour_name || sku.swatch_hex) && (
        <section aria-label="Colour">
          <p className="firstout-header-search__preview-label">Colour</p>
          <p className="firstout-header-search__preview-colour">
            {sku.swatch_hex && <span style={{ background: sku.swatch_hex }} aria-hidden="true" />}
            {sku.colour_name} {sku.swatch_hex && <code>{sku.swatch_hex}</code>}
          </p>
        </section>
      )}
      <section aria-label="Next arrival">
        <p className="firstout-header-search__preview-label">Next arrival</p>
        <p>{nextArrivalText(stock.next_arrival)}</p>
      </section>
    </>
  );
}

export function HeaderSearch({ className, administrationUser }: HeaderSearchProps) {
  const router = useRouter();
  const panel = useSkuPanel();
  const input = useRef<HTMLInputElement>(null);
  const panelId = useId();
  const listId = useId();
  const optionId = (index: number) => `${listId}-option-${index}`;
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [highlight, setHighlight] = useState(0);
  const term = query.trim();
  const searched = useDebouncedValue(term, 250);
  const search = useQuery({
    queryKey: ["search", { term: searched }],
    queryFn: ({ signal }) => searchAll(searched, signal),
    enabled: Boolean(searched),
  });
  // Only answers for what is typed now count; older terms read as still searching.
  const current = searched === term;
  const results = current ? search.data : undefined;
  const searchError = current && search.error ? search.error.message || "Search failed." : undefined;
  const panelOpen = open && !!term;

  const { groups, options } = searchGroups(results, searchAdminDestinations(term, administrationUser));
  const index = options.length ? Math.min(Math.max(highlight, 0), options.length - 1) : -1;
  const active: SearchOption | undefined = options[index];

  // Live preview of the highlighted SKU: debounced, and an old request is dropped when the highlight moves on.
  const highlightedSku = panelOpen && active?.kind === "sku" ? active.hit.id : null;
  const previewId = useDebouncedValue(highlightedSku, PREVIEW_DELAY_MS);
  const preview = useQuery({
    queryKey: catalogueListKeys.skuOverview(previewId ?? ""),
    queryFn: ({ signal }) => getSkuOverview(previewId ?? "", signal),
    enabled: Boolean(previewId) && previewId === highlightedSku,
    staleTime: 30_000,
  });

  // "/" and Ctrl/Cmd+K open search from anywhere that is not already taking keys.
  useEffect(() => {
    function onKeyDown(event: globalThis.KeyboardEvent) {
      const slash = event.key === "/" && !event.metaKey && !event.ctrlKey && !event.altKey;
      const commandK = event.key.toLowerCase() === "k" && (event.metaKey || event.ctrlKey) && !event.altKey;
      if (!slash && !commandK) return;
      if (event.defaultPrevented || keysBelongToTarget(event.target as HTMLElement | null) || document.querySelector(".cds--modal.is-visible")) return;
      event.preventDefault();
      input.current?.focus();
      input.current?.select();
      setOpen(true);
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  function choose(option: SearchOption) {
    if (option.kind === "sku" && panel) {
      // Dock beside the current page; the results become what ↑ ↓ step through. The term stays for later.
      setOpen(false);
      panel.open(option.hit.id, { ids: skuIds(options), label: term, key: "search" });
      requestAnimationFrame(() => document.querySelector<HTMLElement>("[data-sku-panel]")?.focus({ preventScroll: true }));
      return;
    }
    setOpen(false);
    setQuery("");
    router.push(option.href);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape" && panelOpen) {
      event.preventDefault();
      event.stopPropagation();
      input.current?.focus();
      setOpen(false);
      return;
    }
    if (event.target !== input.current || !term) return;
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp" && event.key !== "Enter") return;
    event.preventDefault();
    if (!panelOpen) {
      setOpen(true);
      return;
    }
    if (event.key === "Enter") {
      if (active) choose(active);
      return;
    }
    const next = moveHighlight(index, event.key === "ArrowDown" ? 1 : -1, options.length);
    setHighlight(next);
    document.getElementById(optionId(next))?.scrollIntoView({ block: "nearest" });
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
        placeholder="Search…  /"
        closeButtonLabelText="Clear search"
        value={query}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={panelOpen}
        aria-controls={panelOpen ? listId : undefined}
        aria-activedescendant={panelOpen && index >= 0 ? optionId(index) : undefined}
        aria-keyshortcuts="/ Control+K Meta+K"
        autoComplete="off"
        onChange={(event) => { setQuery(event.target.value); setHighlight(0); setOpen(true); }}
        onClear={() => { setQuery(""); setOpen(false); }}
        onFocus={() => setOpen(true)}
      />
      {panelOpen && (
        <Theme theme="g10">
          <div className="firstout-header-search__panel" id={panelId}>
            <div className="firstout-header-search__body">
              <div className="firstout-header-search__results" role="listbox" id={listId} aria-label="Search results">
                {groups.map(({ label, options: rows }) => (
                  <div role="group" aria-label={label} key={label}>
                    <p className="firstout-header-search__group" aria-hidden="true">{label} · {rows.length}</p>
                    {rows.map(({ option, index: at }) => (
                      <Link
                        key={option.key}
                        id={optionId(at)}
                        href={option.href}
                        role="option"
                        aria-selected={at === index}
                        tabIndex={-1}
                        prefetch={false}
                        className="firstout-header-search__hit"
                        onMouseMove={() => { if (at !== index) setHighlight(at); }}
                        onClick={(event) => {
                          if (!plainClick(event)) return;
                          event.preventDefault();
                          choose(option);
                        }}
                      >
                        {option.kind === "sku" ? (
                          <>
                            <SkuThumb
                              sku={{ id: option.hit.id, swatch_hex: null, photo_storage_key: null, gallery_photo_count: option.hit.has_photo ? 1 : 0 }}
                              className="firstout-header-search__thumb"
                            />
                            <span className="firstout-header-search__text">
                              <span className="firstout-header-search__name">
                                {option.hit.name}
                                {option.hit.is_kit && <Tag size="sm" type="gray">Kit</Tag>}
                              </span>
                              <span className="firstout-header-search__meta"><code>{option.hit.our_ref}</code>{option.hit.category ? ` · ${option.hit.category}` : ""}</span>
                            </span>
                            <span className="firstout-header-search__qty"><strong>{formatCount(option.hit.available)}</strong> available</span>
                            <span className="firstout-header-search__price">{formatZarAmount(option.hit.retail_inc_vat)}</span>
                          </>
                        ) : (
                          <span className="firstout-header-search__text">
                            <span className="firstout-header-search__name">{option.label}</span>
                            {option.meta && <span className="firstout-header-search__meta">{option.meta}</span>}
                          </span>
                        )}
                      </Link>
                    ))}
                  </div>
                ))}
                <div role="status">
                  {!results && !searchError && !groups.length && <p className="firstout-header-search__empty">Searching…</p>}
                  {searchError && <p className="firstout-header-search__empty">{searchError}</p>}
                  {results && !groups.length && <p className="firstout-header-search__empty">No matches for “{term}”.</p>}
                </div>
              </div>
              {active && (
                <aside className="firstout-header-search__preview" aria-label="Preview">
                  {active.kind === "sku" ? (
                    preview.data && previewId === active.hit.id ? <SkuPreview data={preview.data} /> : preview.error && previewId === active.hit.id ? (
                      <p className="firstout-header-search__preview-help">Preview unavailable. Press Enter to open it.</p>
                    ) : (
                      <div className="firstout-loading-motion" aria-hidden="true"><SkeletonText heading width="70%" /><SkeletonText paragraph lineCount={4} /></div>
                    )
                  ) : (
                    <>
                      <p className="firstout-header-search__preview-name">{active.label}</p>
                      {active.meta && <p className="firstout-header-search__preview-help">{active.meta}</p>}
                      <p className="firstout-header-search__preview-help">Enter opens it.</p>
                    </>
                  )}
                </aside>
              )}
            </div>
            <p className="firstout-header-search__foot" aria-hidden="true">
              <span><kbd>↑</kbd> <kbd>↓</kbd> move</span>
              <span><kbd>Enter</kbd> {active?.kind === "link" ? "open" : "open beside this page"}</span>
              <span><kbd>Esc</kbd> close</span>
            </p>
          </div>
        </Theme>
      )}
    </div>
  );
}

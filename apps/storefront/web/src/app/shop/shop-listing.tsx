"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useSyncExternalStore } from "react";
import { ListFilter } from "lucide-react";
import { Badge, Button, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Sheet, SheetClose, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle, SheetTrigger } from "@f0rge/ui";
import { Checkbox } from "@f0rge/ui/forms";
import { countLabel } from "@/components/category-tiles";
import { ProductCard } from "@/components/product-card";
import { SearchResultsTracker } from "@/components/analytics/search-results-tracker";
import type { ListedPiece } from "@/lib/medusa";
import { SHOP_CATEGORIES } from "@/lib/shop-categories";
import { AVAILABILITY_OPTIONS, PRICE_BANDS, SORT_OPTIONS, availableShopAvailability, readShopFilters, shopFacetCount, shopMatches, writeShopFilters, type ShopFilters, type SortKey } from "@/lib/shop-filters";

type FilterGroup = "categories" | "price" | "availability";

const FILTER_CHANGE_EVENT = "storefront-shop-filters-changed";
const currentSearch = () => window.location.search;

function subscribeToSearch(onChange: () => void) {
  window.addEventListener("popstate", onChange);
  window.addEventListener(FILTER_CHANGE_EVENT, onChange);
  return () => {
    window.removeEventListener("popstate", onChange);
    window.removeEventListener(FILTER_CHANGE_EVENT, onChange);
  };
}

export function ShopListing({ pieces, categoryId, shopAll, heading, blurb }: {
  pieces: ListedPiece[]; categoryId?: string; shopAll: boolean; heading: string; blurb: string;
}) {
  const routedSearch = useSearchParams().toString();
  // The browser URL owns the filters. Update the controlled checkboxes immediately
  // on a local pushState while Next synchronizes its navigation state.
  const search = useSyncExternalStore(subscribeToSearch, currentSearch, () => routedSearch ? `?${routedSearch}` : "");
  const offered = availableShopAvailability(pieces);
  const availabilityChoices = offered.length > 1 ? offered : [];
  const filters = readShopFilters(new URLSearchParams(search), shopAll, availabilityChoices);
  const shown = shopMatches(pieces, filters);
  const selectionCount = filters.categories.length + filters.price.length + filters.availability.length;

  function changeFilters(revised: ShopFilters) {
    const url = new URL(window.location.href);
    url.search = writeShopFilters(url.searchParams, revised);
    if (url.href === window.location.href) return;
    window.history.pushState(null, "", url);
    window.dispatchEvent(new Event(FILTER_CHANGE_EVENT));
  }

  function toggle<Group extends FilterGroup>(group: Group, value: ShopFilters[Group][number]) {
    const selected: readonly string[] = filters[group];
    changeFilters({
      ...filters, [group]: selected.includes(value) ? selected.filter((item) => item !== value) : [...selected, value],
    });
  }

  function fieldset<Group extends FilterGroup>(
    where: string, title: string, group: Group, options: readonly { value: ShopFilters[Group][number]; label: string }[],
  ) {
    const selected: readonly string[] = filters[group];
    return <fieldset className="space-y-3">
      <legend className="mb-3 text-sm font-medium">{title}</legend>
      {options.map(({ value, label }) => <Checkbox
        key={value}
        id={`${where}-${group}-${value}`}
        checked={selected.includes(value)}
        onChange={() => toggle(group, value)}
        label={<>{label} <span className="text-muted-foreground">({shopFacetCount(pieces, filters, group, value)})</span></>}
      />)}
    </fieldset>;
  }

  const filterControls = (where: string) => <div className="space-y-6">
    {shopAll && fieldset(where, "Category", "categories", SHOP_CATEGORIES.map(({ handle, name }) => ({ value: handle, label: name })))}
    {fieldset(where, "Price", "price", PRICE_BANDS)}
    {availabilityChoices.length > 0 && fieldset(where, "Availability", "availability", AVAILABILITY_OPTIONS.filter(({ value }) => availabilityChoices.includes(value)))}
  </div>;
  const clear = () => changeFilters({ ...filters, categories: [], price: [], availability: [] });
  const trackedCategory = filters.categories.length === 1
    ? pieces.flatMap((piece) => piece.categories ?? []).find((item) => item.handle === filters.categories[0])?.id
    : categoryId;

  return <>
    <section aria-labelledby="listing-title" className="bg-primary text-primary-foreground">
      <div className="mx-auto max-w-7xl px-4 pt-3.5 pb-1.5 sm:px-6 lg:flex lg:items-center lg:justify-between lg:px-8 lg:py-16">
        <div className="flex flex-wrap items-baseline gap-x-3 lg:block">
          <h1 id="listing-title" className="text-2xl leading-tight font-bold tracking-tight lg:text-4xl">{heading}</h1>
          <p role="status" className="text-sm whitespace-nowrap text-primary-foreground/80 lg:hidden">{countLabel(shown.length)}</p>
          <p className="hidden text-4xl font-bold tracking-tight text-primary-foreground/80 lg:block">{blurb}</p>
        </div>
        <div className="flex flex-wrap gap-x-4 lg:ml-4 lg:shrink-0 lg:gap-3">
          <Button size="lg" variant="secondary" className="max-lg:h-8 max-lg:rounded-none max-lg:border-0 max-lg:bg-transparent max-lg:p-0 max-lg:text-xs max-lg:text-primary-foreground max-lg:underline max-lg:underline-offset-4" nativeButton={false} role="link" render={<Link href="/#visit" />}>Visit the showroom</Button>
          <Button size="lg" variant="ghost" className="text-primary-foreground hover:bg-primary/80 hover:text-primary-foreground max-lg:h-8 max-lg:rounded-none max-lg:p-0 max-lg:text-xs max-lg:underline max-lg:underline-offset-4" nativeButton={false} role="link" render={<Link href="/help" />}>Delivery and returns</Button>
        </div>
      </div>
    </section>
    <div className="mx-auto w-full max-w-7xl p-4 md:p-6">
      <SearchResultsTracker queryPresent={false} categoryId={trackedCategory} priceFilterActive={filters.price.length > 0} resultCount={shown.length}
        availability={filters.availability.length === 1 ? (filters.availability[0] === "in-stock" ? "in_stock" : "made_to_order") : "all"}
        sortOrder={filters.sort === "price-asc" ? "price_asc" : filters.sort === "price-desc" ? "price_desc" : "default"} />
      <div className="flex flex-col gap-8 lg:flex-row">
        <aside aria-label="Filters" className="hidden w-64 shrink-0 lg:block">
          <div className="mb-4 flex min-h-8 items-center justify-between">
            <h2 className="text-lg font-semibold">Filters</h2>
            {selectionCount > 0 && <Button variant="ghost" size="sm" onClick={clear}>Clear all</Button>}
          </div>
          {filterControls("sidebar")}
        </aside>

        <div className="min-w-0 flex-1">
          <div className="mb-3 grid grid-cols-[minmax(6rem,.85fr)_minmax(0,1.45fr)] items-center gap-2.5 lg:mb-4 lg:flex lg:justify-between">
            <Sheet>
              <SheetTrigger render={<Button variant="outline" size="sm" className="h-11 w-full min-w-0 gap-2 lg:hidden" />}>
                <ListFilter aria-hidden className="size-4" />Filters
                {selectionCount > 0 && <Badge variant="secondary" className="ml-1">{selectionCount}</Badge>}
              </SheetTrigger>
              <SheetContent side="bottom" className="max-h-[85dvh]">
                <SheetHeader className="border-b">
                  <SheetTitle>Filters</SheetTitle>
                  <SheetDescription>Narrow the list to find a piece that suits your space.</SheetDescription>
                </SheetHeader>
                <div className="min-h-0 overflow-y-auto px-4 py-2">{filterControls("drawer")}</div>
                <SheetFooter className="shrink-0 flex-row justify-between border-t">
                  <Button variant="outline" onClick={clear}>Clear all</Button>
                  <SheetClose render={<Button />}>Show {countLabel(shown.length)}</SheetClose>
                </SheetFooter>
              </SheetContent>
            </Sheet>
            <p role="status" className="hidden text-sm text-muted-foreground lg:block">{countLabel(shown.length)}</p>
            <Select items={SORT_OPTIONS} value={filters.sort} onValueChange={(value) => value && changeFilters({ ...filters, sort: value as SortKey })}>
              <SelectTrigger className="w-full min-w-0 max-lg:data-[size=default]:h-11 lg:w-48" aria-label="Sort by"><SelectValue /></SelectTrigger>
              <SelectContent>
                {SORT_OPTIONS.map(({ value, label }) => <SelectItem key={value} value={value}>{label}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          {shown.length > 0
            ? <>
              <h2 id="shop-pieces-title" className="sr-only">Pieces</h2>
              <ul aria-labelledby="shop-pieces-title" className="grid grid-cols-2 gap-x-2.5 gap-y-[22px] md:grid-cols-3 md:gap-x-5 md:gap-y-9">
                {shown.map((piece, index) => <ProductCard key={piece.id} piece={piece} initialVariantId={piece.variant?.id} eager={index < 3} />)}
              </ul>
            </>
            : <div className="py-12 text-center">
              <h2 className="text-lg font-medium">No pieces found</h2>
              <p className="mt-1 text-muted-foreground">{pieces.length ? "Try clearing a filter." : "New pieces arrive in the showroom often. Visit us or try another category."}</p>
              {selectionCount > 0 && <Button variant="link" onClick={clear}>Clear filters</Button>}
            </div>}
        </div>
      </div>
    </div>
  </>;
}

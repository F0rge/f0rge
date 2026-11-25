"use client";

import { useSearchParams } from "next/navigation";
import { useSyncExternalStore } from "react";
import { ListFilter } from "lucide-react";
import { Badge, Button, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Sheet, SheetClose, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle, SheetTrigger } from "@f0rge/ui";
import { Checkbox } from "@f0rge/ui/forms";
import { countLabel } from "@/components/category-tiles";
import { ProductCardGallery } from "@/components/product-card-gallery";
import { SearchResultsTracker } from "@/components/analytics/search-results-tracker";
import { TrackedProductLink } from "@/components/analytics/tracked-product-link";
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

export function ShopListing({ pieces, categoryId, shopAll }: { pieces: ListedPiece[]; categoryId?: string; shopAll: boolean }) {
  const routedSearch = useSearchParams().toString();
  // The browser URL owns the filters. Update the controlled checkboxes immediately
  // on a local pushState while Next synchronizes its navigation state.
  const search = useSyncExternalStore(subscribeToSearch, currentSearch, () => routedSearch ? `?${routedSearch}` : "");
  const offered = availableShopAvailability(pieces);
  const availabilityChoices = offered.length > 1 ? offered : [];
  const showFilters = shopAll || availabilityChoices.length > 0;
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
    {shopAll && fieldset(where, "Price", "price", PRICE_BANDS)}
    {availabilityChoices.length > 0 && fieldset(where, "Availability", "availability", AVAILABILITY_OPTIONS.filter(({ value }) => availabilityChoices.includes(value)))}
  </div>;
  const clear = () => changeFilters({ ...filters, categories: [], price: [], availability: [] });
  const trackedCategory = filters.categories.length === 1
    ? pieces.flatMap((piece) => piece.categories ?? []).find((item) => item.handle === filters.categories[0])?.id
    : categoryId;

  return <div className="mx-auto w-full max-w-7xl p-4 md:p-6">
    <SearchResultsTracker queryPresent={false} categoryId={trackedCategory} priceFilterActive={filters.price.length > 0} resultCount={shown.length}
      availability={filters.availability.length === 1 ? (filters.availability[0] === "in-stock" ? "in_stock" : "made_to_order") : "all"}
      sortOrder={filters.sort === "price-asc" ? "price_asc" : filters.sort === "price-desc" ? "price_desc" : "default"} />
    <div className="flex flex-col gap-8 lg:flex-row">
      {showFilters && <div className="lg:hidden">
        <Sheet>
          <SheetTrigger render={<Button variant="outline" size="sm" className="gap-2" />}>
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
      </div>}

      {showFilters && <aside aria-label="Filters" className="hidden w-64 shrink-0 lg:block">
        <div className="mb-4 flex min-h-8 items-center justify-between">
          <h2 className="text-lg font-semibold">Filters</h2>
          {selectionCount > 0 && <Button variant="ghost" size="sm" onClick={clear}>Clear all</Button>}
        </div>
        {filterControls("sidebar")}
      </aside>}

      <div className="min-w-0 flex-1">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <p role="status" className="text-sm text-muted-foreground">{countLabel(shown.length)}</p>
          <Select items={SORT_OPTIONS} value={filters.sort} onValueChange={(value) => value && changeFilters({ ...filters, sort: value as SortKey })}>
            <SelectTrigger className="w-48" aria-label="Sort by"><SelectValue /></SelectTrigger>
            <SelectContent>
              {SORT_OPTIONS.map(({ value, label }) => <SelectItem key={value} value={value}>{label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>

        {shown.length > 0
          ? <ul aria-label="Pieces" className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-3">
            {shown.map((piece, index) => <li key={piece.id} data-product-card className="min-w-0 overflow-hidden rounded-xl border bg-card">
              <ProductCardGallery key={piece.variant?.id} title={piece.title} images={piece.variant?.images ?? []} prioritizeFirstImage={index === 0} />
              <TrackedProductLink href={piece.href} productId={piece.id} className="flex items-center justify-between gap-4 p-4 hover:underline">
                <h3 className="line-clamp-2 min-w-0 font-medium">{piece.title}</h3>
                <div className="text-right">
                  <p className="font-medium whitespace-nowrap">{piece.priceLabel}</p>
                  <p className="text-sm text-muted-foreground">{piece.stockLabel}</p>
                </div>
              </TrackedProductLink>
            </li>)}
          </ul>
          : <div className="py-12 text-center">
            <h2 className="text-lg font-medium">No pieces found</h2>
            <p className="mt-1 text-muted-foreground">{pieces.length ? "Try clearing a filter." : "New pieces arrive in the showroom often. Visit us or try another category."}</p>
          </div>}
      </div>
    </div>
  </div>;
}

"use client";

import { useState } from "react";
import { ListFilter } from "lucide-react";
import { Badge, Button, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Sheet, SheetClose, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle, SheetTrigger } from "@f0rge/ui";
import { Checkbox } from "@f0rge/ui/forms";
import { countLabel } from "@/components/category-tiles";
import { PieceImage } from "@/components/piece-image";
import { SearchResultsTracker } from "@/components/analytics/search-results-tracker";
import { TrackedProductLink } from "@/components/analytics/tracked-product-link";
import type { Availability, ListedPiece } from "@/lib/medusa";

const AVAILABILITY: { value: Availability; label: string }[] = [
  { value: "in-stock", label: "In stock" },
  { value: "made-to-order", label: "Made to order" },
];

// A piece without a price sorts last either way.
const SORTS = {
  name: { label: "Name, A to Z", compare: (a: ListedPiece, b: ListedPiece) => a.title.localeCompare(b.title, "en-ZA") },
  "price-asc": { label: "Price, low to high", compare: (a: ListedPiece, b: ListedPiece) => (a.price ?? Infinity) - (b.price ?? Infinity) },
  "price-desc": { label: "Price, high to low", compare: (a: ListedPiece, b: ListedPiece) => (b.price ?? -Infinity) - (a.price ?? -Infinity) },
} as const;
type SortKey = keyof typeof SORTS;

export function ShopListing({ pieces, categoryId }: { pieces: ListedPiece[]; categoryId?: string }) {
  const [chosen, setChosen] = useState<Availability[]>([]);
  const [sort, setSort] = useState<SortKey>("name");
  // Counts and grid both come from `pieces`, so a count always matches what ticking it shows.
  const options = AVAILABILITY.map((option) => ({ ...option, count: pieces.filter((piece) => piece.availability.includes(option.value)).length }))
    .filter((option) => option.count > 0);
  const shown = pieces.filter((piece) => !chosen.length || piece.availability.some((value) => chosen.includes(value))).sort(SORTS[sort].compare);
  const toggle = (value: Availability) => setChosen((current) => current.includes(value) ? current.filter((item) => item !== value) : [...current, value]);

  const filters = (where: string) => options.length > 0 && <fieldset className="space-y-3">
    <legend className="mb-3 text-sm font-medium">Availability</legend>
    {options.map((option) => <Checkbox key={option.value} id={`${where}-${option.value}`} checked={chosen.includes(option.value)} onChange={() => toggle(option.value)}
      label={<>{option.label} <span className="text-muted-foreground">({option.count})</span></>} />)}
  </fieldset>;
  const clear = chosen.length > 0 && <Button variant="ghost" size="sm" onClick={() => setChosen([])}>Clear all</Button>;

  return <div className="mx-auto w-full max-w-7xl p-4 md:p-6">
    <SearchResultsTracker queryPresent={false} categoryId={categoryId} priceFilterActive={false} resultCount={shown.length}
      availability={chosen.length === 1 ? (chosen[0] === "in-stock" ? "in_stock" : "made_to_order") : "all"}
      sortOrder={sort === "price-asc" ? "price_asc" : sort === "price-desc" ? "price_desc" : "default"} />
    <div className="flex flex-col gap-8 lg:flex-row">
      <div className="lg:hidden">
        <Sheet>
          <SheetTrigger render={<Button variant="outline" size="sm" className="gap-2" />}>
            <ListFilter aria-hidden="true" className="size-4" />Filters
            {chosen.length > 0 && <Badge variant="secondary" className="ml-1">{chosen.length}</Badge>}
          </SheetTrigger>
          <SheetContent side="bottom">
            <SheetHeader className="border-b">
              <SheetTitle>Filters</SheetTitle>
              <SheetDescription>Narrow the list by availability.</SheetDescription>
            </SheetHeader>
            <div className="px-4 py-2">{filters("drawer")}</div>
            <SheetFooter className="flex-row justify-between border-t">
              <Button variant="outline" onClick={() => setChosen([])}>Clear all</Button>
              <SheetClose render={<Button />}>Show {countLabel(shown.length)}</SheetClose>
            </SheetFooter>
          </SheetContent>
        </Sheet>
      </div>

      <aside aria-label="Filters" className="hidden w-64 shrink-0 lg:block">
        <div className="mb-4 flex min-h-8 items-center justify-between">
          <h2 className="text-lg font-semibold">Filters</h2>
          {clear}
        </div>
        {filters("sidebar")}
      </aside>

      <div className="min-w-0 flex-1">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <p role="status" className="text-sm text-muted-foreground">{countLabel(shown.length)}</p>
          <Select items={Object.entries(SORTS).map(([value, { label }]) => ({ value, label }))} value={sort} onValueChange={(value) => value && setSort(value as SortKey)}>
            <SelectTrigger className="w-48" aria-label="Sort by"><SelectValue /></SelectTrigger>
            <SelectContent>
              {Object.entries(SORTS).map(([value, { label }]) => <SelectItem key={value} value={value}>{label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>

        {shown.length > 0
          ? <ul aria-label="Pieces" className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-3">
            {shown.map((piece) => <li key={piece.id}>
              <TrackedProductLink href={piece.href} productId={piece.id} className="group block h-full overflow-hidden rounded-xl border bg-card">
                <div className="relative aspect-square overflow-hidden bg-muted"><PieceImage product={piece} /></div>
                <div className="flex items-center justify-between gap-4 p-4">
                  <h3 className="line-clamp-2 min-w-0 font-medium">{piece.title}</h3>
                  <div className="text-right">
                    <p className="font-medium whitespace-nowrap">{piece.priceLabel}</p>
                    {piece.stockLabel && <p className="text-sm text-muted-foreground">{piece.stockLabel}</p>}
                  </div>
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

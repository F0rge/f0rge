import type { Availability, ListedPiece, ListedVariant } from "./medusa";
import { SHOP_CATEGORIES, type ShopCategory } from "./shop-categories";

export const AVAILABILITY_OPTIONS = [
  { value: "in-stock", label: "In stock" },
  { value: "made-to-order", label: "Made to order" },
] as const;

export const PRICE_BANDS = [
  { value: "under-7500", label: "Under R7 500", min: 0, max: 7_500 },
  { value: "7500-15000", label: "R7 500 to under R15 000", min: 7_500, max: 15_000 },
  { value: "15000-30000", label: "R15 000 to under R30 000", min: 15_000, max: 30_000 },
  { value: "30000-up", label: "R30 000 and up", min: 30_000, max: Infinity },
] as const;

const SORTS = {
  name: { label: "Name, A to Z", compare: (a: ShopMatch, b: ShopMatch) => a.title.localeCompare(b.title, "en-ZA") },
  "price-asc": { label: "Price, low to high", compare: (a: ShopMatch, b: ShopMatch) => (a.price ?? Infinity) - (b.price ?? Infinity) },
  "price-desc": { label: "Price, high to low", compare: (a: ShopMatch, b: ShopMatch) => (b.price ?? -Infinity) - (a.price ?? -Infinity) },
} as const;

export const variantHref = (href: string, variantId: string) => `${href.split("?")[0]}?variant=${encodeURIComponent(variantId)}`;

export type SortKey = keyof typeof SORTS;
type PriceBand = (typeof PRICE_BANDS)[number]["value"];
type CategoryHandle = ShopCategory["handle"];

export type ShopFilters = {
  categories: CategoryHandle[];
  price: PriceBand[];
  availability: Availability[];
  sort: SortKey;
};

type Search = Pick<URLSearchParams, "getAll" | "get">;
export type ShopMatch = ListedPiece & { variant?: ListedVariant };

export const SORT_OPTIONS = Object.entries(SORTS).map(([value, { label }]) => ({ value, label }));
const isSort = (value: string | null): value is SortKey => value !== null && Object.hasOwn(SORTS, value);

export function readShopFilters(params: Search, showShopFacets: boolean, availabilityChoices: Availability[]): ShopFilters {
  const sort = params.get("sort");
  const categories = params.getAll("categories");
  const price = params.getAll("price");
  const availability = params.getAll("availability");
  return {
    categories: showShopFacets ? SHOP_CATEGORIES.map(({ handle }) => handle).filter((handle) => categories.includes(handle)) : [],
    price: showShopFacets ? PRICE_BANDS.map(({ value }) => value).filter((value) => price.includes(value)) : [],
    availability: availabilityChoices.filter((value) => availability.includes(value)),
    sort: isSort(sort) ? sort : "name",
  };
}

export function writeShopFilters(source: URLSearchParams, filters: ShopFilters): string {
  const params = new URLSearchParams(source);
  for (const key of ["categories", "price", "availability"] as const) {
    params.delete(key);
    for (const value of filters[key]) params.append(key, value);
  }
  params.delete("sort");
  if (filters.sort !== "name") params.set("sort", filters.sort);
  return params.toString();
}

export function availableShopAvailability(pieces: ListedPiece[]): Availability[] {
  return AVAILABILITY_OPTIONS.map(({ value }) => value)
    .filter((value) => pieces.some(({ variants }) => variants.some(({ availability }) => availability === value)));
}

export function shopMatches(pieces: ListedPiece[], filters: ShopFilters): ShopMatch[] {
  const hasVariantFilter = filters.price.length > 0 || filters.availability.length > 0;
  const prices = PRICE_BANDS.filter(({ value }) => filters.price.includes(value));
  const matches: ShopMatch[] = [];
  for (const piece of pieces) {
    if (filters.categories.length && !piece.categories?.some(({ handle }) => filters.categories.some((selected) => selected === handle))) continue;
    if (!hasVariantFilter) {
      matches.push({ ...piece, variant: piece.variants[0] });
      continue;
    }
    const variant = piece.variants.find(({ price, availability }) => availability !== null &&
      (!filters.availability.length || filters.availability.includes(availability)) &&
      (!prices.length || (price !== null && prices.some(({ min, max }) => price >= min && price < max))));
    if (!variant) continue;
    matches.push({
      ...piece, price: variant.price, priceLabel: variant.priceLabel,
      href: piece.variants.length > 1 ? variantHref(piece.href, variant.id) : piece.href,
      variant,
    });
  }
  return matches.sort(SORTS[filters.sort].compare);
}

type FilterGroup = "categories" | "price" | "availability";

export function shopFacetCount<Group extends FilterGroup>(pieces: ListedPiece[], filters: ShopFilters, group: Group, value: ShopFilters[Group][number]): number {
  return shopMatches(pieces, { ...filters, sort: "name", [group]: [value] }).length;
}

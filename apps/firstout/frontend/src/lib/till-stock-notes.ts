import type { InventorySku } from "./api";
import type { TillAvailability } from "./till-reservations";

// ponytail: a guess at "low" (one or fewer left at the showroom); tune it once the showrooms say what they need.
export const LOW_STOCK_THRESHOLD = 1;

/** One SKU's stock as the till sees it; staff-only, never printed on the invoice. */
export type TillStock = {
  row: InventorySku | undefined;
  locationId: string;
  /** The till's showroom, e.g. Bedfordview. */
  locationName: string;
  /** Active showroom and warehouse locations: the stock the company can sell. */
  sellableLocationIds: ReadonlySet<string>;
  /** Units of this SKU already in the sale. */
  inCart: number;
};

function split({ row, locationId, sellableLocationIds }: TillStock) {
  const locations = row?.locations ?? [];
  const here = locations.find((loc) => loc.location_id === locationId)?.on_hand ?? 0;
  const elsewhere = locations
    .filter((loc) => loc.location_id !== locationId && loc.on_hand > 0 && sellableLocationIds.has(loc.location_id))
    .sort((a, b) => b.on_hand - a.on_hand)
    .map((loc) => loc.location_name);
  return { here, elsewhere: namedLocations(elsewhere) };
}

/** "Warehouse", "Warehouse, Kramerville", "Warehouse, Kramerville +1 more". */
export function namedLocations(names: readonly string[]): string {
  if (!names.length) return "another location";
  const shown = names.slice(0, 2).join(", ");
  return names.length > 2 ? `${shown} +${names.length - 2} more` : shown;
}

/** The one-line stock state under a search result or product tile (stock-tracked SKUs only). */
export function resultStockState(stock: TillStock, availability: TillAvailability): string {
  if (availability.reason) return availability.reason;
  const { here, elsewhere } = split(stock);
  const hereLeft = Math.min(here - stock.inCart, availability.addable);
  if (hereLeft > LOW_STOCK_THRESHOLD) return `${hereLeft} at ${stock.locationName}`;
  if (hereLeft > 0) return `Low stock · last ${hereLeft} at ${stock.locationName}`;
  if (availability.addable > 0) return `Not at ${stock.locationName} · ${availability.addable} at ${elsewhere}`;
  return "All in this sale";
}

/** A basket line's stock note, or null when the showroom covers it with stock to spare. */
export function basketStockNote(stock: TillStock): string | null {
  const { here, elsewhere } = split(stock);
  const fromHere = Math.max(0, Math.min(here, stock.inCart));
  const away = stock.inCart - fromHere;
  if (away > 0) {
    return fromHere ? `${fromHere} here · ${away} from ${elsewhere}` : `Not at ${stock.locationName} · ${away} at ${elsewhere}`;
  }
  return here - stock.inCart <= LOW_STOCK_THRESHOLD ? `Low stock · last ${here} at ${stock.locationName}` : null;
}

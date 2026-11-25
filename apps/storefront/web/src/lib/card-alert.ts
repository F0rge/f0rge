import type { ListedPiece, ListedVariant } from "./medusa";
import { formatWholeZar } from "./order-money";

export type CardAlert =
  | { kind: "sale"; percent: number; saving: string }
  | { kind: "just-arrived" }
  | { kind: "made-to-order" };

/** A sale worth announcing: at least 1% off. Both figures round down so the card never overstates the saving. */
export function saleOf(variant: Pick<ListedVariant, "price" | "was"> | undefined): { percent: number; saving: string } | null {
  if (variant?.price == null || variant.was == null || variant.was <= variant.price) return null;
  const percent = Math.floor(((variant.was - variant.price) / variant.was) * 100);
  return percent >= 1 ? { percent, saving: formatWholeZar(variant.was - variant.price) } : null;
}

/** At most one alert per card, in this order: sale, just arrived, made to order. */
export function cardAlert(piece: Pick<ListedPiece, "justArrived" | "variants">, shown: ListedVariant | undefined): CardAlert | null {
  const sale = saleOf(shown);
  if (sale) return { kind: "sale", ...sale };
  if (piece.justArrived) return { kind: "just-arrived" };
  const availability = piece.variants.map((variant) => variant.availability);
  return !availability.includes("in-stock") && availability.includes("made-to-order") ? { kind: "made-to-order" } : null;
}

/** Finish dots only when every listed variant of a multi-variant piece has a colour. */
export function showSwatches(piece: Pick<ListedPiece, "variants">): boolean {
  return piece.variants.length > 1 && piece.variants.every((variant) => variant.swatch);
}

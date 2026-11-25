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

const AVAILABILITY_RANK = { "in-stock": 0, "made-to-order": 1 } as const;
const rank = (variant: ListedVariant) => variant.availability ? AVAILABILITY_RANK[variant.availability] : 2;
// Available before unavailable, then cheapest first; the sort is stable, so ties keep Medusa's order.
const preferred = (a: ListedVariant, b: ListedVariant) => rank(a) - rank(b) || (a.price ?? Infinity) - (b.price ?? Infinity);

/** The variant a card opens on: the one asked for, else the lowest-priced (the "From" price and the sort use it). */
export function startVariant(piece: Pick<ListedPiece, "variants">, variantId?: string): ListedVariant | undefined {
  return piece.variants.find(({ id }) => id === variantId)
    ?? [...piece.variants].sort((a, b) => (a.price ?? Infinity) - (b.price ?? Infinity))[0];
}

export type Finish = { swatch: string; name: string; variant: ListedVariant };

/**
 * One finish dot per distinct colour, each opening its best variant (available, then cheapest).
 * None unless every variant has a colour and there are at least two colours.
 * The name is the option values every variant of that colour shares, such as "Gold" for Gold / 160 cm and Gold / 200 cm.
 */
export function finishChoices(piece: Pick<ListedPiece, "variants">): Finish[] {
  if (!piece.variants.every((variant) => variant.swatch)) return [];
  const groups = new Map<string, ListedVariant[]>();
  for (const variant of piece.variants) groups.set(variant.swatch!, [...(groups.get(variant.swatch!) ?? []), variant]);
  if (groups.size < 2) return [];
  return [...groups].map(([swatch, variants]) => {
    const shared = variants[0].options.filter((value) => variants.every(({ options }) => options.includes(value)));
    const variant = [...variants].sort(preferred)[0];
    return { swatch, name: shared.join(" / ") || variant.name, variant };
  });
}

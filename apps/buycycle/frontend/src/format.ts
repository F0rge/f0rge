import type { Listing } from "./api/client";
import type { Category } from "./state";
export const money = (value: number | null | undefined) =>
  value == null
    ? "Not observed"
    : new Intl.NumberFormat("en-LU", {
        style: "currency",
        currency: "EUR",
        maximumFractionDigits: 0,
      }).format(value);
export const number = (value: number | null | undefined, digits = 1) =>
  value == null
    ? "Not observed"
    : value.toLocaleString("en-LU", { maximumFractionDigits: digits });
export function returns(
  listing: Listing,
  costs: Category["costs"],
): { profit: number | null; roi: number | null } {
  if (
    listing.reference_price == null ||
    ![
      "bp",
      "bpf",
      "pay",
      "shipin",
      "pack",
      "repair",
      "buffer",
      "haircut",
      "sellfee",
      "shipout",
      "relist",
    ].every(
      (key) => typeof costs[key] === "number" && Number.isFinite(costs[key]),
    )
  )
    return { profit: null, roi: null };
  const c = (key: string) => costs[key] ?? 0;
  const sale = listing.reference_price * (1 - c("haircut") / 100);
  const cost =
    listing.price * (1 + c("bp") / 100) +
    c("bpf") +
    (listing.price * c("pay")) / 100 +
    c("shipin") +
    c("pack") +
    c("repair") +
    c("buffer");
  const profit =
    sale * (1 - c("sellfee") / 100) - c("shipout") - c("relist") - cost;
  return { profit, roi: cost > 0 ? (profit / cost) * 100 : null };
}
export function safeUrl(value: string): string | undefined {
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:"
      ? url.href
      : undefined;
  } catch {
    return undefined;
  }
}

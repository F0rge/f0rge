import { conflictCode, type ApiError, type InventorySku, type TillBasket, type TillBlockingReservation, type TillReservation } from "./api";

const clock = new Intl.DateTimeFormat("en-ZA", {
  hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: "Africa/Johannesburg",
});
const showroomDate = new Intl.DateTimeFormat("en-ZA", {
  day: "numeric", month: "short", year: "numeric", timeZone: "Africa/Johannesburg",
});

/** 24-hour showroom time (Africa/Johannesburg) for an ISO timestamp. */
export function tillClock(iso: string): string {
  return clock.format(new Date(iso));
}

function expiryDateTime(iso: string): string {
  return `${showroomDate.format(new Date(iso))} at ${tillClock(iso)}`;
}

// A basket ID belongs to a single cashier and showroom. Keep only its last displayed expiry.
const fallbackExpiries = new Map<string, string>();
const expiryStorageKey = (basketId: string) => `firstout.till.shownExpiry.${basketId}`;

export function hasShownBasketExpiry(basketId: string, expiredAt: string): boolean {
  if (fallbackExpiries.get(basketId) === expiredAt) return true;
  try {
    return window.localStorage.getItem(expiryStorageKey(basketId)) === expiredAt;
  } catch {
    return false;
  }
}

export function rememberBasketExpiry(basketId: string, expiredAt: string): void {
  try {
    window.localStorage.setItem(expiryStorageKey(basketId), expiredAt);
  } catch {
    // Storage can be unavailable on a shared till. Navigation still remembers the notice.
    fallbackExpiries.set(basketId, expiredAt);
  }
}

/** Why a SKU cannot be added; names the showroom only, never the cashier or customer. */
export function reservationReason(blocking: TillBlockingReservation | null): string {
  if (!blocking) return "Reserved in another sale";
  const where = blocking.holder_kind === "basket" ? "in open sale"
    : blocking.holder_kind === "held_sale" ? "in held sale" : "for an invoice";
  const frees = blocking.expires_at ? ` · frees ${tillClock(blocking.expires_at)} unless sold` : "";
  return `Reserved ${where} at ${blocking.location_name}${frees}`;
}

export type TillAvailability = {
  /** Units this till may hold in total: the company's unreserved stock at any active location. */
  limit: number;
  /** Units it can still add on top of the cart. */
  addable: number;
  /** Set when other sales' reservations are what stops it. */
  reason: string | null;
};

/** Refresh at the first advertised deadline. The server decides which units are still held. */
export function reservationRefreshInterval(rows: TillReservation[] | undefined, now: number): number | false {
  let earliest = Infinity;
  for (const row of rows ?? []) {
    if (row.blocking?.expires_at) earliest = Math.min(earliest, Date.parse(row.blocking.expires_at));
  }
  if (!Number.isFinite(earliest)) return false;
  // After a failed refresh or with a fast client clock, give the server time before retrying.
  return earliest > now ? earliest - now : 15_000;
}

/** The server re-checks every add; this only decides what the till offers. */
export function tillAvailability({ row, sellableLocationIds, reservation, inCart }: {
  row: InventorySku | undefined;
  /** Active showroom and warehouse locations: the stock the company can sell. */
  sellableLocationIds: ReadonlySet<string>;
  reservation: TillReservation | undefined;
  inCart: number;
}): TillAvailability {
  const company = (row?.locations ?? []).reduce(
    (sum, loc) => sellableLocationIds.has(loc.location_id) ? sum + loc.on_hand : sum, 0,
  );
  // The server splits a sale: the showroom's units deduct now, the rest is picked against the invoice.
  const limit = Math.max(0, company - (reservation?.reserved_by_others ?? 0));
  const addable = Math.max(0, limit - inCart);
  const blocked = reservation && addable === 0 && company - inCart > 0;
  return { limit, addable, reason: blocked ? reservationReason(reservation.blocking) : null };
}

export type TillNotice = { kind: "info" | "warning"; title: string; subtitle?: string };

const RELEASE = "The items stay reserved until then; after that the sale is deleted and the stock released.";

/** The Current sale header: low-contrast info, a warning in the last 15 minutes. */
export function expiryNotice(expiresAt: string, now: number, holdHours?: number): TillNotice {
  const time = tillClock(expiresAt);
  const left = Date.parse(expiresAt) - now;
  if (left <= 0) {
    return { kind: "warning", title: `This sale expired on ${expiryDateTime(expiresAt)}.`, subtitle: "Its items were released. Add them again." };
  }
  if (left <= 15 * 60_000) {
    const minutes = Math.ceil(left / 60_000);
    return {
      kind: "warning",
      title: `Expires at ${time}, in ${minutes} ${minutes === 1 ? "minute" : "minutes"}.`,
      subtitle: "After that the sale is deleted and the stock released.",
    };
  }
  const after = holdHours ? `, ${holdHours} ${holdHours === 1 ? "hour" : "hours"} after the last change` : "";
  return { kind: "info", title: `This sale expires at ${time}${after}.`, subtitle: RELEASE };
}

const URGENT_MS = 15 * 60_000;

export type HeldTimeLeft = {
  expired: boolean;
  /** The last 15 minutes: marked with a warning tag. */
  urgent: boolean;
  /** Whole minutes left, rounded up; 0 once expired. */
  minutes: number;
  /** "2 h 10 min", "45 min"; empty once expired. */
  duration: string;
  /** Table cell text: "2 h 10 min · 14:28", or "Expired". */
  label: string;
};

/** How long a held sale keeps its stock reserved. */
export function heldTimeLeft(expiresAt: string, now: number): HeldTimeLeft {
  const left = Date.parse(expiresAt) - now;
  if (left <= 0) return { expired: true, urgent: false, minutes: 0, duration: "", label: "Expired" };
  const minutes = Math.ceil(left / 60_000);
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  const duration = hours ? `${hours} h${rest ? ` ${rest} min` : ""}` : `${rest} min`;
  return { expired: false, urgent: left <= URGENT_MS, minutes, duration, label: `${duration} · ${tillClock(expiresAt)}` };
}

/** The one line above the Held sales table. */
export function heldSalesExplainer(holdHours?: number): string {
  if (!holdHours) {
    return "Held sales keep their stock reserved for the hold time from when they were held. " +
      "After that they are deleted and the stock released. Resuming a sale starts the hold time again.";
  }
  const span = `${holdHours} ${holdHours === 1 ? "hour" : "hours"}`;
  return `Held sales keep their stock reserved for ${span} from when they were held. ` +
    `After that they are deleted and the stock released. Resuming a sale starts a new ${span}.`;
}

/** The selected held sale's warning; null while it is not yet in its last 15 minutes. */
export function heldExpiryNotice(expiresAt: string, now: number): TillNotice | null {
  const left = heldTimeLeft(expiresAt, now);
  const time = tillClock(expiresAt);
  if (left.expired) {
    return { kind: "warning", title: `Expired at ${time}.`, subtitle: "It is deleted and the stock released." };
  }
  if (!left.urgent) return null;
  return {
    kind: "warning",
    title: `Expires at ${time}, in ${left.minutes} ${left.minutes === 1 ? "minute" : "minutes"}.`,
    subtitle: "Resume it to keep the stock reserved. Otherwise it is deleted and the stock released.",
  };
}

export function expiredMessage(expiredAt: string): string {
  return `Your sale expired on ${expiryDateTime(expiredAt)}. Its items were released. Add them again.`;
}

/** A 409 that carries the server's current basket for the till to show instead of its own. */
export type BasketConflict = {
  code: string;
  message?: string;
  basket?: TillBasket;
  sku_id?: string;
  available?: number;
  blocking?: TillBlockingReservation | null;
};

export function basketConflict(error: unknown): BasketConflict | null {
  return conflictCode(error) ? (error as ApiError).detail as BasketConflict : null;
}

/** What the till says after adopting the server basket from a conflict. */
export function conflictNotice(conflict: BasketConflict, skuName: (id: string) => string | undefined): TillNotice {
  if (conflict.code === "stock_reserved") {
    const name = (conflict.sku_id && skuName(conflict.sku_id)) || "This item";
    return {
      kind: "warning",
      title: `${name} was not added`,
      subtitle: conflict.blocking
        ? `${reservationReason(conflict.blocking)}.`
        : conflict.message ?? "There is not enough unreserved stock.",
    };
  }
  if (conflict.code === "basket_expired") {
    const expiredAt = conflict.basket?.expired_at;
    return {
      kind: "warning",
      title: "Sale expired",
      subtitle: expiredAt ? expiredMessage(expiredAt) : "Your sale expired. Its items were released. Add them again.",
    };
  }
  if (conflict.code === "held_sale_expired") {
    return {
      kind: "warning",
      title: "Held sale expired",
      subtitle: conflict.message ?? "It was deleted and its stock released.",
    };
  }
  return { kind: "info", title: "Basket updated elsewhere", subtitle: "The till now shows the latest saved basket." };
}

import { picksCreateHref } from "@/lib/picks";

export type TillKitPickReason = "missing_parts" | "split_pick";

export type TillKitBlock = {
  sku_id: string;
  sku_code: string;
  sku_name: string;
  qty: number;
  location_id: string;
  location_name: string;
  reason: TillKitPickReason;
  message: string;
};

export type TillCartSnapshot = {
  locationId: string;
  customerId: string;
  pickId: string;
  linkedPickIds: Record<string, string>;
  lines: { skuId: string; qty: number; discountPercent: number }[];
};

export type TillKitSaleState<TCart> = {
  cart: TCart[];
  pickId: string;
  linkedPickIds: Record<string, string>;
  blocks: TillKitBlock[];
};

type KeyValueStore = {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
};

const TILL_CART_KEY = "firstout.till.cart";

function browserSession(): KeyValueStore | null {
  if (typeof sessionStorage === "undefined") {
    return null;
  }
  return sessionStorage;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}

function parseBlock(value: unknown): TillKitBlock | null {
  const row = asRecord(value);
  if (!row) {
    return null;
  }
  const reason = row.reason;
  if (reason !== "missing_parts" && reason !== "split_pick") {
    return null;
  }
  const skuId = row.sku_id;
  const skuCode = row.sku_code;
  const skuName = row.sku_name;
  const locationId = row.location_id;
  const locationName = row.location_name;
  const message = row.message;
  const qty = row.qty;
  if (
    typeof skuId !== "string" ||
    typeof skuCode !== "string" ||
    typeof skuName !== "string" ||
    typeof locationId !== "string" ||
    typeof locationName !== "string" ||
    typeof message !== "string" ||
    typeof qty !== "number"
  ) {
    return null;
  }
  return {
    sku_id: skuId,
    sku_code: skuCode,
    sku_name: skuName,
    qty,
    location_id: locationId,
    location_name: locationName,
    reason,
    message,
  };
}

export function parseKitRequiresPick(
  detail: unknown,
): { message: string; kits: TillKitBlock[] } | null {
  const row = asRecord(detail);
  if (!row || row.code !== "kit_requires_pick" || !Array.isArray(row.kits)) {
    return null;
  }
  const kits = row.kits
    .map(parseBlock)
    .filter((kit): kit is TillKitBlock => kit !== null);
  if (kits.length === 0) {
    return null;
  }
  const message =
    typeof row.message === "string" && row.message.trim()
      ? row.message
      : kits.map((kit) => kit.message).join(" ");
  return { message, kits };
}

/** Open-picks link for this block, not whichever kit happens to be first in the cart. */
export function openPicksHrefForKit(kit: Pick<TillKitBlock, "sku_id" | "qty">): string {
  return picksCreateHref(kit.sku_id, kit.qty);
}

export function salePickIds(linkedPickIds: Record<string, string>, pickId: string): string[] {
  const ids: string[] = [];
  for (const id of Object.values(linkedPickIds)) {
    if (id && !ids.includes(id)) {
      ids.push(id);
    }
  }
  if (pickId && !ids.includes(pickId)) {
    ids.push(pickId);
  }
  return ids;
}

export function nextTillStateAfterKitConfirm<TCart>(
  state: TillKitSaleState<TCart>,
  confirmed: { id: string; skuId: string },
): TillKitSaleState<TCart> {
  return {
    cart: state.cart,
    pickId: confirmed.id,
    linkedPickIds: { ...state.linkedPickIds, [confirmed.skuId]: confirmed.id },
    blocks: state.blocks.filter((block) => block.sku_id !== confirmed.skuId),
  };
}

export function saveTillCart(snapshot: TillCartSnapshot, store?: KeyValueStore): void {
  const target = store ?? browserSession();
  if (!target) {
    return;
  }
  target.setItem(TILL_CART_KEY, JSON.stringify(snapshot));
}

export function loadTillCart(store?: KeyValueStore): TillCartSnapshot | null {
  const target = store ?? browserSession();
  if (!target) {
    return null;
  }
  const raw = target.getItem(TILL_CART_KEY);
  if (!raw) {
    return null;
  }
  try {
    const parsed = JSON.parse(raw) as unknown;
    const row = asRecord(parsed);
    if (!row || !Array.isArray(row.lines)) {
      return null;
    }
    const lines = row.lines.flatMap((line) => {
      const item = asRecord(line);
      if (!item || typeof item.skuId !== "string") {
        return [];
      }
      const qty = typeof item.qty === "number" ? item.qty : 1;
      const discountPercent = typeof item.discountPercent === "number" ? item.discountPercent : 0;
      return [{ skuId: item.skuId, qty, discountPercent }];
    });
    const linked = asRecord(row.linkedPickIds);
    const linkedPickIds: Record<string, string> = {};
    if (linked) {
      for (const [skuId, pickId] of Object.entries(linked)) {
        if (typeof pickId === "string") {
          linkedPickIds[skuId] = pickId;
        }
      }
    }
    return {
      locationId: typeof row.locationId === "string" ? row.locationId : "",
      customerId: typeof row.customerId === "string" ? row.customerId : "",
      pickId: typeof row.pickId === "string" ? row.pickId : "",
      linkedPickIds,
      lines,
    };
  } catch {
    return null;
  }
}

export function clearTillCart(store?: KeyValueStore): void {
  const target = store ?? browserSession();
  target?.removeItem(TILL_CART_KEY);
}

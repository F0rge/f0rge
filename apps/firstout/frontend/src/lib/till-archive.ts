import type { PickDocument, Sku } from "./api";
import type { TillCartSnapshot } from "./till-kit-pick";

/** Only server-origin till commitments can resume; normalized display fallbacks are insufficient. */
export function isPendingTillPick(pick: PickDocument): boolean {
  return pick.source_type === "till"
    && !!pick.kit_sku_id
    && typeof pick.kit_qty === "number" && pick.kit_qty > 0
    && ["confirmed", "picking", "staged"].includes(pick.status)
    && pick.invoice_id === null;
}

/** Firstout's timezone-free server datetimes represent UTC, never browser-local time. */
function serverTimestamp(value: string | null | undefined): number {
  const timestamp = value?.trim();
  if (!timestamp) return Number.NaN;
  const hasTimezone = /(?:z|[+-]\d{2}:?\d{2})$/i.test(timestamp);
  return Date.parse(hasTimezone ? timestamp : `${timestamp}Z`);
}

export function canResumeArchivedTillPick(
  sku: Sku,
  pick: PickDocument | undefined,
  qty: number,
  customerId: string,
): boolean {
  if (!pick || !sku.is_archived || !sku.is_sellable || !sku.is_kit || !isPendingTillPick(pick)) return false;
  const archivedAt = serverTimestamp(sku.archived_at);
  const createdAt = serverTimestamp(pick.created_at);
  return pick.kit_sku_id === sku.id && pick.kit_qty === qty
    && Number.isFinite(archivedAt) && Number.isFinite(createdAt) && createdAt <= archivedAt
    && (!pick.customer_id || pick.customer_id === customerId);
}

/** Fetch an archived SKU only through a saved line's concrete, eligible till pick. */
export async function restoreTillCartSkus(
  snapshot: TillCartSnapshot,
  activeSkus: Sku[],
  picks: PickDocument[],
  getSku: (id: string) => Promise<Sku>,
): Promise<Map<string, Sku>> {
  const byId = new Map(activeSkus.filter((sku) => !sku.is_archived).map((sku) => [sku.id, sku]));
  for (const line of snapshot.lines) {
    if (byId.has(line.skuId)) continue;
    const pickId = snapshot.linkedPickIds[line.skuId] || snapshot.pickId;
    const pick = picks.find((item) => item.id === pickId);
    if (!pick || !isPendingTillPick(pick) || pick.kit_sku_id !== line.skuId || pick.kit_qty !== line.qty) continue;
    const sku = await getSku(line.skuId);
    if (canResumeArchivedTillPick(sku, pick, line.qty, snapshot.customerId)) byId.set(sku.id, sku);
  }
  return byId;
}

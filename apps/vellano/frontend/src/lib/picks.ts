export const KIT_REQUIRES_PICK_MESSAGE = "Kit requires pick";
export const CONFIRM_SPLIT_REQUIRED_MESSAGE = "confirm_split required";

export type PickStatus = "draft" | "confirmed" | "picking" | "staged" | "cancelled";

export type PickAllocation = {
  location_id: string;
  location_name: string;
  on_hand: number;
  qty: number;
};

export type PickLine = {
  sku_id: string;
  sku_our_ref: string;
  sku_name: string;
  qty_needed: number;
  allocations: PickAllocation[];
};

export type PickDocument = {
  id: string;
  pick_number: string;
  status: PickStatus;
  sku_id: string;
  sku_our_ref: string;
  sku_name: string;
  qty: number;
  customer_id: string | null;
  invoice_id: string | null;
  layby_id: string | null;
  needs_confirm: boolean;
  qty_short: boolean;
  staging_location_id: string | null;
  collect_from_showroom: boolean;
  lines: PickLine[];
  created_at: string;
  updated_at: string;
};

export type PickPreviewLocation = {
  location_id: string;
  location_name: string;
  on_hand: number;
  suggested_qty: number;
};

export type PickPreviewLine = {
  sku_id: string;
  sku_our_ref: string;
  sku_name: string;
  qty_needed: number;
  qty_short: number;
  locations: PickPreviewLocation[];
};

export type PickPreview = {
  sku_id: string;
  qty: number;
  needs_confirm: boolean;
  qty_short: boolean;
  lines: PickPreviewLine[];
};

export type CreatePickPayload =
  | { sku_id: string; qty: number; customer_id?: string }
  | { invoice_id: string }
  | { layby_id: string };

export type UpdatePickPayload = {
  lines: { sku_id: string; allocations: { location_id: string; qty: number }[] }[];
};

export type PickQtyMap = Record<string, Record<string, number>>;

export const PICK_STATUS_LABELS: Record<PickStatus, string> = {
  draft: "Draft",
  confirmed: "Confirmed",
  picking: "Picking",
  staged: "Staged",
  cancelled: "Cancelled",
};

const PICK_STATUSES = new Set<string>(Object.keys(PICK_STATUS_LABELS));

export function pickStatusTagType(
  status: PickStatus,
): "blue" | "teal" | "purple" | "green" | "gray" {
  if (status === "draft") {
    return "blue";
  }
  if (status === "confirmed") {
    return "teal";
  }
  if (status === "picking") {
    return "purple";
  }
  if (status === "staged") {
    return "green";
  }
  return "gray";
}

export function isKitRequiresPickMessage(message: string): boolean {
  return message === KIT_REQUIRES_PICK_MESSAGE || message.includes(KIT_REQUIRES_PICK_MESSAGE);
}

export function isConfirmSplitRequiredMessage(message: string): boolean {
  return (
    message === CONFIRM_SPLIT_REQUIRED_MESSAGE ||
    message.toLowerCase().includes(CONFIRM_SPLIT_REQUIRED_MESSAGE)
  );
}

export function firstWarehouseId(
  locations: { id: string; type: string; is_archived: boolean }[],
): string {
  return locations.find((loc) => !loc.is_archived && loc.type === "warehouse")?.id ?? "";
}

export function picksCreateHref(skuId: string, qty: number): string {
  const params = new URLSearchParams();
  params.set("sku", skuId);
  params.set("qty", String(qty));
  return `/picks?${params.toString()}`;
}

export function isPickEditable(status: PickStatus): boolean {
  return status === "draft";
}

export function canConfirmPick(status: PickStatus): boolean {
  return status === "draft";
}

export function canCompletePick(status: PickStatus): boolean {
  return status === "confirmed" || status === "picking";
}

export function canCancelPick(status: PickStatus): boolean {
  return status === "draft" || status === "confirmed";
}

function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function asList(value: unknown): unknown[] {
  if (Array.isArray(value)) {
    return value;
  }
  const row = asRecord(value);
  const nested = row.picks ?? row.items ?? row.data ?? row.lines ?? row.locations ?? row.allocations;
  return Array.isArray(nested) ? nested : [];
}

function pickString(row: Record<string, unknown>, keys: string[], fallback = ""): string {
  for (const key of keys) {
    const value = row[key];
    if (typeof value === "string") {
      return value;
    }
    if (typeof value === "number" && Number.isFinite(value)) {
      return String(value);
    }
  }
  return fallback;
}

function pickNumber(row: Record<string, unknown>, keys: string[], fallback = 0): number {
  for (const key of keys) {
    const value = row[key];
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }
    if (typeof value === "string" && value.trim() !== "") {
      const parsed = Number(value);
      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }
  }
  return fallback;
}

function pickBool(row: Record<string, unknown>, keys: string[], fallback: boolean): boolean {
  for (const key of keys) {
    const value = row[key];
    if (typeof value === "boolean") {
      return value;
    }
  }
  return fallback;
}

function pickNullable(row: Record<string, unknown>, keys: string[]): string | null {
  const value = pickString(row, keys);
  return value || null;
}

function normalizeAllocation(value: unknown): PickAllocation {
  const row = asRecord(value);
  return {
    location_id: pickString(row, ["location_id", "locationId"]),
    location_name: pickString(row, ["location_name", "locationName", "name"]),
    on_hand: pickNumber(row, ["on_hand", "onhand", "qty_on_hand"]),
    qty: pickNumber(row, ["qty", "suggested_qty", "suggested", "qty_suggested"]),
  };
}

function normalizeLine(value: unknown): PickLine {
  const row = asRecord(value);
  const allocations = asList(row.allocations ?? row.locations ?? row.cells).map(normalizeAllocation);
  return {
    sku_id: pickString(row, ["sku_id", "component_sku_id", "skuId"]),
    sku_our_ref: pickString(row, ["sku_our_ref", "our_ref", "skuOurRef"]),
    sku_name: pickString(row, ["sku_name", "name", "skuName"]),
    qty_needed: pickNumber(row, ["qty_needed", "qty", "required_qty"]),
    allocations,
  };
}

export function normalizePick(value: unknown): PickDocument {
  const row = asRecord(value);
  const statusRaw = pickString(row, ["status"]);
  return {
    id: pickString(row, ["id"]),
    pick_number: pickString(row, ["pick_number", "number", "pickNumber"]),
    status: PICK_STATUSES.has(statusRaw) ? (statusRaw as PickStatus) : "draft",
    sku_id: pickString(row, ["sku_id", "kit_sku_id", "skuId"]),
    sku_our_ref: pickString(row, ["kit_sku_our_ref", "sku_our_ref", "our_ref", "skuOurRef"]),
    sku_name: pickString(row, ["kit_sku_name", "sku_name", "name", "skuName"]),
    qty: pickNumber(row, ["qty", "kit_qty"]),
    customer_id: pickNullable(row, ["customer_id", "customerId"]),
    invoice_id: pickNullable(row, ["invoice_id", "invoiceId"]),
    layby_id: pickNullable(row, ["layby_id", "laybyId"]),
    needs_confirm: pickBool(row, ["needs_confirm", "needs_confirmation"], false),
    qty_short: pickBool(row, ["qty_short", "short"], false),
    staging_location_id: pickNullable(row, ["staging_location_id", "stagingLocationId"]),
    collect_from_showroom: pickBool(row, ["collect_from_showroom", "collectFromShowroom"], false),
    lines: asList(row.lines ?? row.components).map(normalizeLine),
    created_at: pickString(row, ["created_at", "createdAt"]),
    updated_at: pickString(row, ["updated_at", "updatedAt"]),
  };
}

export function normalizePickList(value: unknown): PickDocument[] {
  return asList(value).map(normalizePick).filter((entry) => entry.id);
}

function normalizePreviewLocation(value: unknown): PickPreviewLocation {
  const row = asRecord(value);
  return {
    location_id: pickString(row, ["location_id", "locationId"]),
    location_name: pickString(row, ["location_name", "locationName", "name"]),
    on_hand: pickNumber(row, ["on_hand", "onhand", "qty_on_hand"]),
    suggested_qty: pickNumber(row, ["suggested_qty", "suggested", "qty_suggested", "qty"]),
  };
}

function normalizePreviewLine(value: unknown): PickPreviewLine {
  const row = asRecord(value);
  return {
    sku_id: pickString(row, ["sku_id", "component_sku_id", "skuId"]),
    sku_our_ref: pickString(row, ["sku_our_ref", "our_ref", "skuOurRef"]),
    sku_name: pickString(row, ["sku_name", "name", "skuName"]),
    qty_needed: pickNumber(row, ["qty_needed", "qty", "required_qty"]),
    qty_short: pickNumber(row, ["qty_short", "short_qty", "short"]),
    locations: asList(row.locations ?? row.allocations).map(normalizePreviewLocation),
  };
}

export function normalizePreview(value: unknown): PickPreview {
  const row = asRecord(value);
  return {
    sku_id: pickString(row, ["sku_id", "kit_sku_id", "skuId"]),
    qty: pickNumber(row, ["qty", "kit_qty"]),
    needs_confirm: pickBool(row, ["needs_confirm", "needs_confirmation"], false),
    qty_short: pickBool(row, ["qty_short", "short"], false) || pickNumber(row, ["qty_short"]) > 0,
    lines: asList(row.lines ?? row.components).map(normalizePreviewLine),
  };
}

export function normalizePickSettings(value: unknown): {
  always_prefer_warehouse: boolean;
  pick_priority: string[];
} {
  const row = asRecord(value);
  const rawPriority = row.pick_priority ?? row.pickPriority ?? row.pick_priority_location_ids;
  const pick_priority = Array.isArray(rawPriority)
    ? rawPriority.filter((entry): entry is string => typeof entry === "string" && entry.length > 0)
    : [];
  return {
    always_prefer_warehouse: pickBool(row, ["always_prefer_warehouse", "alwaysPreferWarehouse"], true),
    pick_priority,
  };
}

export function qtyMapFromAllocations(lines: PickLine[]): PickQtyMap {
  const next: PickQtyMap = {};
  for (const line of lines) {
    next[line.sku_id] = {};
    for (const allocation of line.allocations) {
      next[line.sku_id][allocation.location_id] = allocation.qty;
    }
  }
  return next;
}

export function qtyMapFromPreview(preview: PickPreview): PickQtyMap {
  const next: PickQtyMap = {};
  for (const line of preview.lines) {
    next[line.sku_id] = {};
    for (const location of line.locations) {
      next[line.sku_id][location.location_id] = location.suggested_qty;
    }
  }
  return next;
}

export function onHandFromPreview(preview: PickPreview): Record<string, Record<string, number>> {
  const next: Record<string, Record<string, number>> = {};
  for (const line of preview.lines) {
    next[line.sku_id] = {};
    for (const location of line.locations) {
      next[line.sku_id][location.location_id] = location.on_hand;
    }
  }
  return next;
}

export function onHandFromLines(lines: PickLine[]): Record<string, Record<string, number>> {
  const next: Record<string, Record<string, number>> = {};
  for (const line of lines) {
    next[line.sku_id] = {};
    for (const allocation of line.allocations) {
      next[line.sku_id][allocation.location_id] = allocation.on_hand;
    }
  }
  return next;
}

export function allocationsPayload(lines: PickLine[], qty: PickQtyMap): UpdatePickPayload {
  return {
    lines: lines.map((line) => ({
      sku_id: line.sku_id,
      allocations: Object.entries(qty[line.sku_id] ?? {})
        .map(([location_id, amount]) => ({ location_id, qty: amount }))
        .filter((entry) => entry.qty > 0),
    })),
  };
}

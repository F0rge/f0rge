"use client";

import { Button, ComboBox, NumberInput, Stack } from "@carbon/react";
import { Checkmark } from "@carbon/icons-react";
import { useMemo, useRef, useState } from "react";

import {
  ADJUSTMENT_REASON_LABELS,
  addAdjustmentLine,
  cancelAdjustment,
  completeAdjustment,
  deleteAdjustmentLine,
  formatPriceAmount,
  patchAdjustmentLine,
  type Adjustment,
  type AdjustmentLine,
  type InventorySku,
  type Sku,
} from "@/lib/api";

import {
  AdjustmentLinesTable,
  draftFromLine,
  lineEffectiveCost,
  type LineDraft,
  type LineDraftValue,
} from "./adjustment-lines-table";

type AdjustmentDraftProps = {
  adjustment: Adjustment;
  locationName: string;
  skus: Sku[];
  inventory: InventorySku[];
  canMutate: boolean;
  onLinesChanged: (lines: AdjustmentLine[]) => void;
  onFinished: () => Promise<void>;
  onError: (message: string) => void;
};

function formatDateTime(iso: string | undefined): string {
  if (!iso) {
    return "—";
  }
  return new Date(iso).toLocaleString("en-ZA");
}

export function skuItemToString(item: Sku | null): string {
  if (!item) {
    return "";
  }
  return `${item.our_ref} — ${item.name}`;
}

function shouldFilterSku({
  item,
  itemToString,
  inputValue,
}: {
  item: Sku;
  itemToString?: (item: Sku | null) => string;
  inputValue: string | null;
}): boolean {
  if (!inputValue) {
    return true;
  }
  const haystack = (itemToString ?? skuItemToString)(item).toLowerCase();
  return haystack.includes(inputValue.toLowerCase());
}

function draftsFromLines(
  lines: AdjustmentLine[],
  inventory: InventorySku[],
  locationId: string,
): Record<string, LineDraft> {
  const next: Record<string, LineDraft> = {};
  for (const line of lines) {
    next[line.id] = draftFromLine(line, inventory, locationId);
  }
  return next;
}

function isCostDirty(
  line: AdjustmentLine,
  draft: LineDraft,
  inventory: InventorySku[],
  locationId: string,
): boolean {
  if (typeof draft.unit_cost !== "number" || draft.unit_cost <= 0) {
    return false;
  }
  const baseline = lineEffectiveCost(line, inventory, locationId);
  if (baseline === null) {
    return true;
  }
  return formatPriceAmount(draft.unit_cost) !== formatPriceAmount(baseline);
}

function isQtyDirty(line: AdjustmentLine, draft: LineDraft): boolean {
  return (
    typeof draft.qty_delta === "number" &&
    draft.qty_delta !== 0 &&
    draft.qty_delta !== line.qty_delta
  );
}

export function AdjustmentDraft({
  adjustment,
  locationName,
  skus,
  inventory,
  canMutate,
  onLinesChanged,
  onFinished,
  onError,
}: AdjustmentDraftProps) {
  const [skuId, setSkuId] = useState("");
  const [qtyDelta, setQtyDelta] = useState<number | "">("");
  const [unitCost, setUnitCost] = useState<number | "">("");
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [drafts, setDrafts] = useState<Record<string, LineDraft>>(() =>
    draftsFromLines(adjustment.lines, inventory, adjustment.location_id),
  );
  const draftsRef = useRef(drafts);

  const addedSkuIds = useMemo(
    () => new Set(adjustment.lines.map((line) => line.sku_id)),
    [adjustment.lines],
  );
  const skuOptions = useMemo(
    () => skus.filter((sku) => !addedSkuIds.has(sku.id)),
    [addedSkuIds, skus],
  );
  const selectedSku = skuOptions.find((sku) => sku.id === skuId) ?? null;
  const numericDelta = typeof qtyDelta === "number" ? qtyDelta : 0;
  const canAdd = canMutate && Boolean(skuId) && qtyDelta !== "" && numericDelta !== 0;

  function setDraftField(lineId: string, field: keyof LineDraft, value: LineDraftValue) {
    setDrafts((current) => {
      const line = adjustment.lines.find((entry) => entry.id === lineId);
      const prev =
        current[lineId] ??
        (line
          ? draftFromLine(line, inventory, adjustment.location_id)
          : { qty_delta: "" as const, unit_cost: "" as const });
      const next = { ...current, [lineId]: { ...prev, [field]: value } };
      draftsRef.current = next;
      return next;
    });
  }

  function seedDraft(line: AdjustmentLine) {
    setDrafts((current) => {
      const next = {
        ...current,
        [line.id]: draftFromLine(line, inventory, adjustment.location_id),
      };
      draftsRef.current = next;
      return next;
    });
  }

  function dropDraft(lineId: string) {
    setDrafts((current) => {
      const next = { ...current };
      delete next[lineId];
      draftsRef.current = next;
      return next;
    });
  }

  async function patchLine(line: AdjustmentLine): Promise<AdjustmentLine | null> {
    const draft = draftsRef.current[line.id];
    if (!canMutate || !draft) {
      return null;
    }
    const payload: { qty_delta?: number; unit_cost_zar?: string } = {};
    if (isQtyDirty(line, draft)) {
      payload.qty_delta = Math.trunc(draft.qty_delta as number);
    }
    if (isCostDirty(line, draft, inventory, adjustment.location_id)) {
      payload.unit_cost_zar = formatPriceAmount(draft.unit_cost as number);
    }
    if (payload.qty_delta === undefined && payload.unit_cost_zar === undefined) {
      return null;
    }
    const updated = await patchAdjustmentLine(adjustment.id, line.id, payload);
    seedDraft(updated);
    return updated;
  }

  async function saveLine(lineId: string): Promise<void> {
    const line = adjustment.lines.find((entry) => entry.id === lineId);
    if (!line) {
      return;
    }
    const updated = await patchLine(line);
    if (updated) {
      onLinesChanged(adjustment.lines.map((entry) => (entry.id === updated.id ? updated : entry)));
    }
  }

  async function flushDrafts() {
    let next = [...adjustment.lines];
    for (const line of adjustment.lines) {
      const current = next.find((entry) => entry.id === line.id) ?? line;
      const draft = draftsRef.current[current.id];
      if (!draft || !(isQtyDirty(current, draft) || isCostDirty(current, draft, inventory, adjustment.location_id))) {
        continue;
      }
      const updated = await patchLine(current);
      if (updated) {
        next = next.map((entry) => (entry.id === updated.id ? updated : entry));
      }
    }
    onLinesChanged(next);
  }

  async function handleAddLine() {
    if (!canAdd) {
      return;
    }
    setAdding(true);
    try {
      const cost =
        typeof unitCost === "number" && Number.isFinite(unitCost)
          ? formatPriceAmount(unitCost)
          : undefined;
      const line = await addAdjustmentLine(adjustment.id, {
        sku_id: skuId,
        qty_delta: numericDelta,
        ...(cost ? { unit_cost_zar: cost } : {}),
      });
      onLinesChanged([...adjustment.lines, line]);
      seedDraft(line);
      setSkuId("");
      setQtyDelta("");
      setUnitCost("");
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to add line.");
    } finally {
      setAdding(false);
    }
  }

  async function handleRemove(lineId: string) {
    if (!canMutate) {
      return;
    }
    setBusy(true);
    try {
      await deleteAdjustmentLine(adjustment.id, lineId);
      dropDraft(lineId);
      onLinesChanged(adjustment.lines.filter((line) => line.id !== lineId));
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to remove line.");
    } finally {
      setBusy(false);
    }
  }

  async function handleLineBlur(lineId: string) {
    try {
      await saveLine(lineId);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to update line.");
    }
  }

  async function handleComplete() {
    if (!canMutate) {
      return;
    }
    setBusy(true);
    try {
      await flushDrafts();
      await completeAdjustment(adjustment.id);
      await onFinished();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to complete adjustment.");
    } finally {
      setBusy(false);
    }
  }

  async function handleCancel() {
    if (!canMutate) {
      return;
    }
    setBusy(true);
    try {
      await cancelAdjustment(adjustment.id);
      await onFinished();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to cancel adjustment.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Stack gap={6}>
      <div className="vellano-page-header">
        <div>
          <h1 className="cds--type-productive-heading-04">Stock Adjustment</h1>
          <p className="cds--type-body-01">
            {locationName} • {ADJUSTMENT_REASON_LABELS[adjustment.reason]} • Draft
            {adjustment.created_at || adjustment.started_at
              ? ` • Started ${formatDateTime(adjustment.created_at ?? adjustment.started_at)}`
              : ""}
          </p>
        </div>
        {canMutate ? (
          <div style={{ display: "flex", gap: "0.75rem" }}>
            <Button kind="danger" disabled={busy || adding} onClick={() => void handleCancel()}>
              Cancel
            </Button>
            <Button
              disabled={busy || adding || adjustment.lines.length === 0}
              renderIcon={Checkmark}
              onClick={() => void handleComplete()}
            >
              Complete Adjustment
            </Button>
          </div>
        ) : null}
      </div>

      {canMutate ? (
        <Stack gap={5}>
          <ComboBox
            id="adjustment-sku"
            titleText="SKU"
            placeholder="Type to search..."
            items={skuOptions}
            itemToString={skuItemToString}
            shouldFilterItem={shouldFilterSku}
            selectedItem={selectedSku}
            onChange={({ selectedItem }) => setSkuId(selectedItem?.id ?? "")}
            helperText={
              skuOptions.length === 0 ? "All catalogue SKUs are already on this draft" : undefined
            }
            disabled={busy || adding}
          />
          <NumberInput
            id="adjustment-qty-delta"
            label="Quantity delta"
            helperText="Positive increases on-hand; negative decreases"
            allowEmpty
            step={1}
            value={qtyDelta}
            onChange={(_event, { value }) => {
              setQtyDelta(value === "" ? "" : Number(value));
            }}
          />
          <NumberInput
            id="adjustment-unit-cost"
            label="Unit cost (ZAR)"
            helperText="Optional. Omit to keep the existing location cost."
            allowEmpty
            min={0}
            step={0.01}
            value={unitCost}
            onChange={(_event, { value }) => {
              setUnitCost(value === "" ? "" : Number(value));
            }}
          />
          <Button disabled={!canAdd || adding || busy} onClick={() => void handleAddLine()}>
            {adding ? "Adding…" : "Add Line"}
          </Button>
        </Stack>
      ) : null}

      <AdjustmentLinesTable
        lines={adjustment.lines}
        locationId={adjustment.location_id}
        inventory={inventory}
        canMutate={canMutate}
        busy={busy || adding}
        drafts={canMutate ? drafts : undefined}
        onDraftChange={canMutate ? setDraftField : undefined}
        onLineBlur={canMutate ? (lineId) => void handleLineBlur(lineId) : undefined}
        onRemove={canMutate ? handleRemove : undefined}
      />
    </Stack>
  );
}

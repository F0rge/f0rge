"use client";

import { Button, NumberInput, Select, SelectItem, Stack } from "@carbon/react";
import { Checkmark } from "@carbon/icons-react";
import { useMemo, useState } from "react";

import {
  ADJUSTMENT_REASON_LABELS,
  addAdjustmentLine,
  cancelAdjustment,
  completeAdjustment,
  deleteAdjustmentLine,
  formatPriceAmount,
  type Adjustment,
  type AdjustmentLine,
  type InventorySku,
  type Sku,
} from "@/lib/api";

import { AdjustmentLinesTable } from "./adjustment-lines-table";

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

  const addedSkuIds = useMemo(
    () => new Set(adjustment.lines.map((line) => line.sku_id)),
    [adjustment.lines],
  );
  const skuOptions = skus.filter((sku) => !addedSkuIds.has(sku.id));
  const numericDelta = typeof qtyDelta === "number" ? qtyDelta : 0;
  const canAdd = canMutate && Boolean(skuId) && qtyDelta !== "" && numericDelta !== 0;

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
      onLinesChanged(adjustment.lines.filter((line) => line.id !== lineId));
    } catch (err) {
      onError(err instanceof Error ? err.message : "Failed to remove line.");
    } finally {
      setBusy(false);
    }
  }

  async function handleComplete() {
    if (!canMutate) {
      return;
    }
    setBusy(true);
    try {
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
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-end",
          gap: "1rem",
          flexWrap: "wrap",
        }}
      >
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
          <Select
            id="adjustment-sku"
            labelText="SKU"
            value={skuId}
            onChange={(event) => setSkuId(event.target.value)}
            helperText={
              skuOptions.length === 0 ? "All catalogue SKUs are already on this draft" : undefined
            }
          >
            <SelectItem value="" text="Select a SKU" />
            {skuOptions.map((sku) => (
              <SelectItem key={sku.id} value={sku.id} text={`${sku.our_ref} — ${sku.name}`} />
            ))}
          </Select>
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
        onRemove={canMutate ? handleRemove : undefined}
      />
    </Stack>
  );
}

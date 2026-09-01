"use client";

import { Button, Stack } from "@carbon/react";

import {
  ADJUSTMENT_REASON_LABELS,
  ADJUSTMENT_STATUS_LABELS,
  type Adjustment,
  type InventorySku,
} from "@/lib/api";

import { AdjustmentLinesTable } from "./adjustment-lines-table";

type AdjustmentViewProps = {
  adjustment: Adjustment;
  locationName: string;
  inventory: InventorySku[];
  onBack: () => void;
};

function formatDateTime(iso: string | undefined | null): string {
  if (!iso) {
    return "—";
  }
  return new Date(iso).toLocaleString("en-ZA");
}

export function AdjustmentView({
  adjustment,
  locationName,
  inventory,
  onBack,
}: AdjustmentViewProps) {
  const date = adjustment.completed_at ?? adjustment.created_at ?? adjustment.started_at;
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
            {locationName} • {ADJUSTMENT_REASON_LABELS[adjustment.reason]} •{" "}
            {ADJUSTMENT_STATUS_LABELS[adjustment.status]} • {formatDateTime(date)}
          </p>
          {adjustment.notes ? <p className="cds--type-body-01">{adjustment.notes}</p> : null}
        </div>
        <Button kind="ghost" onClick={onBack}>
          Back to list
        </Button>
      </div>
      <AdjustmentLinesTable
        lines={adjustment.lines}
        locationId={adjustment.location_id}
        inventory={inventory}
        canMutate={false}
        busy={false}
      />
    </Stack>
  );
}

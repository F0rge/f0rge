"use client";

import {
  Button,
  DataTable,
  NumberInput,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
} from "@carbon/react";
import { TrashCan } from "@carbon/icons-react";
import { useMemo } from "react";

import {
  formatPriceAmount,
  formatZarAmount,
  type AdjustmentLine,
  type InventorySku,
} from "@/lib/api";

export type LineDraftValue = number | "";

export type LineDraft = {
  qty_delta: LineDraftValue;
  unit_cost: LineDraftValue;
};

const LINE_HEADERS = [
  { key: "product", header: "Product" },
  { key: "current_qty", header: "Current Qty" },
  { key: "qty_delta", header: "Delta" },
  { key: "new_qty", header: "New Qty" },
  { key: "unit_cost_zar", header: "Unit Cost (ZAR)" },
  { key: "actions", header: "" },
] as const;

type AdjustmentLinesTableProps = {
  lines: AdjustmentLine[];
  locationId: string;
  inventory: InventorySku[];
  canMutate: boolean;
  busy: boolean;
  drafts?: Record<string, LineDraft>;
  onDraftChange?: (lineId: string, field: keyof LineDraft, value: LineDraftValue) => void;
  onLineBlur?: (lineId: string) => void;
  onRemove?: (lineId: string) => void;
};

export function onHandAtLocation(
  inventory: InventorySku[],
  skuId: string,
  locationId: string,
): number {
  const sku = inventory.find((entry) => entry.sku_id === skuId);
  const loc = sku?.locations.find((entry) => entry.location_id === locationId);
  return loc?.on_hand ?? 0;
}

export function unitCostAtLocation(
  inventory: InventorySku[],
  skuId: string,
  locationId: string,
): string | null {
  const sku = inventory.find((entry) => entry.sku_id === skuId);
  const loc = sku?.locations.find((entry) => entry.location_id === locationId);
  return loc?.unit_cost_zar ?? sku?.unit_cost_zar ?? null;
}

export function parseCostAmount(value: string | null | undefined): number | null {
  if (!value) {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function lineCurrentQty(
  line: AdjustmentLine,
  inventory: InventorySku[],
  locationId: string,
): number {
  if (typeof line.current_qty === "number") {
    return line.current_qty;
  }
  return onHandAtLocation(inventory, line.sku_id, locationId);
}

export function lineNewQty(line: AdjustmentLine, currentQty: number, qtyDelta?: number): number {
  if (qtyDelta === undefined && typeof line.new_qty === "number") {
    return line.new_qty;
  }
  return currentQty + (qtyDelta ?? line.qty_delta);
}

export function lineEffectiveCost(
  line: AdjustmentLine,
  inventory: InventorySku[],
  locationId: string,
  draftCost?: LineDraftValue,
): number | null {
  if (typeof draftCost === "number" && Number.isFinite(draftCost)) {
    return draftCost;
  }
  const fromLine = parseCostAmount(line.unit_cost_zar);
  if (fromLine !== null) {
    return fromLine;
  }
  return parseCostAmount(unitCostAtLocation(inventory, line.sku_id, locationId));
}

export function draftFromLine(
  line: AdjustmentLine,
  inventory: InventorySku[],
  locationId: string,
): LineDraft {
  const cost = lineEffectiveCost(line, inventory, locationId);
  return {
    qty_delta: line.qty_delta,
    unit_cost: cost ?? "",
  };
}

export function formatValueImpact(total: number): string {
  const body = formatZarAmount(formatPriceAmount(Math.abs(total)));
  if (total > 0) {
    return `+${body}`;
  }
  if (total < 0) {
    return `-${body}`;
  }
  return body;
}

function formatDelta(delta: number): string {
  if (delta > 0) {
    return `+${delta}`;
  }
  return String(delta);
}

function formatCost(value: number | null): string {
  if (value === null) {
    return "—";
  }
  return formatZarAmount(formatPriceAmount(value));
}

function numberFromInput(value: string | number): LineDraftValue {
  return value === "" ? "" : Number(value);
}

export function AdjustmentLinesTable({
  lines,
  locationId,
  inventory,
  canMutate,
  busy,
  drafts,
  onDraftChange,
  onLineBlur,
  onRemove,
}: AdjustmentLinesTableProps) {
  const showActions = Boolean(canMutate && onRemove);
  const editable = Boolean(canMutate && drafts && onDraftChange && onLineBlur);
  const headers = useMemo(
    () => (showActions ? [...LINE_HEADERS] : LINE_HEADERS.filter((header) => header.key !== "actions")),
    [showActions],
  );
  const rows = useMemo(
    () =>
      lines.map((line) => {
        const currentQty = lineCurrentQty(line, inventory, locationId);
        const draft = drafts?.[line.id];
        const delta =
          typeof draft?.qty_delta === "number" ? draft.qty_delta : line.qty_delta;
        const cost = lineEffectiveCost(line, inventory, locationId, draft?.unit_cost);
        return {
          id: line.id,
          product: line.id,
          current_qty: String(currentQty),
          qty_delta: formatDelta(delta),
          new_qty: String(lineNewQty(line, currentQty, delta)),
          unit_cost_zar: formatCost(cost),
          actions: line.id,
        };
      }),
    [drafts, inventory, lines, locationId],
  );
  const totalImpact = useMemo(
    () =>
      lines.reduce((sum, line) => {
        const draft = drafts?.[line.id];
        const delta =
          typeof draft?.qty_delta === "number" ? draft.qty_delta : line.qty_delta;
        const cost = lineEffectiveCost(line, inventory, locationId, draft?.unit_cost);
        if (cost === null) {
          return sum;
        }
        return sum + delta * cost;
      }, 0),
    [drafts, inventory, lines, locationId],
  );

  if (lines.length === 0) {
    return (
      <p className="cds--type-body-01">No lines yet. Add a SKU to this draft.</p>
    );
  }

  return (
    <DataTable rows={rows} headers={headers}>
      {({ rows: tableRows, headers: tableHeaders, getTableProps, getHeaderProps, getRowProps }) => (
        <TableContainer title="Adjustment lines" description={`${lines.length} line(s)`}>
          <Table {...getTableProps()}>
            <TableHead>
              <TableRow>
                {tableHeaders.map((header) => (
                  <TableHeader {...getHeaderProps({ header })} key={header.key}>
                    {header.header}
                  </TableHeader>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {tableRows.map((row) => {
                const line = lines.find((entry) => entry.id === row.id);
                const draft = drafts?.[row.id];
                return (
                  <TableRow {...getRowProps({ row })} key={row.id}>
                    {row.cells.map((cell) => {
                      if (cell.info.header === "product" && line) {
                        return (
                          <TableCell key={cell.id}>
                            <div>{line.name}</div>
                            <div className="cds--type-label-01">{line.our_ref}</div>
                          </TableCell>
                        );
                      }
                      if (cell.info.header === "qty_delta" && editable) {
                        return (
                          <TableCell key={cell.id}>
                            <div style={{ maxWidth: "6.5rem" }}>
                              <NumberInput
                                id={`adjustment-delta-${row.id}`}
                                label="Delta"
                                hideLabel
                                allowEmpty
                                step={1}
                                size="sm"
                                value={draft?.qty_delta ?? ""}
                                disabled={busy}
                                onChange={(_event, { value }) => {
                                  onDraftChange?.(row.id, "qty_delta", numberFromInput(value));
                                }}
                                onBlur={() => onLineBlur?.(row.id)}
                              />
                            </div>
                          </TableCell>
                        );
                      }
                      if (cell.info.header === "unit_cost_zar" && editable) {
                        return (
                          <TableCell key={cell.id}>
                            <div style={{ maxWidth: "8rem" }}>
                              <NumberInput
                                id={`adjustment-cost-${row.id}`}
                                label="Unit cost"
                                hideLabel
                                allowEmpty
                                min={0}
                                step={0.01}
                                size="sm"
                                value={draft?.unit_cost ?? ""}
                                disabled={busy}
                                onChange={(_event, { value }) => {
                                  onDraftChange?.(row.id, "unit_cost", numberFromInput(value));
                                }}
                                onBlur={() => onLineBlur?.(row.id)}
                              />
                            </div>
                          </TableCell>
                        );
                      }
                      if (cell.info.header === "actions") {
                        return (
                          <TableCell key={cell.id}>
                            {showActions ? (
                              <Button
                                kind="danger--ghost"
                                size="sm"
                                hasIconOnly
                                renderIcon={TrashCan}
                                iconDescription="Remove line"
                                tooltipPosition="left"
                                disabled={busy}
                                onClick={() => onRemove?.(row.id)}
                              />
                            ) : null}
                          </TableCell>
                        );
                      }
                      return <TableCell key={cell.id}>{cell.value}</TableCell>;
                    })}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
          <div
            style={{
              padding: "1rem",
              textAlign: "right",
              backgroundColor: "var(--cds-layer-02, #f4f4f4)",
              borderTop: "1px solid var(--cds-border-subtle-01, #e0e0e0)",
            }}
          >
            <p className="cds--type-label-01" style={{ marginBottom: "0.25rem" }}>
              Total Value Impact (ZAR)
            </p>
            <p className="cds--type-productive-heading-03" style={{ margin: 0 }}>
              {formatValueImpact(totalImpact)}
            </p>
          </div>
        </TableContainer>
      )}
    </DataTable>
  );
}

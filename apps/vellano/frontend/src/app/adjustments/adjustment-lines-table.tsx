"use client";

import {
  Button,
  DataTable,
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

import { formatPriceAmount, type AdjustmentLine, type InventorySku } from "@/lib/api";

const LINE_HEADERS = [
  { key: "product", header: "Product" },
  { key: "current_qty", header: "Current Qty" },
  { key: "qty_delta", header: "Delta" },
  { key: "new_qty", header: "New Qty" },
  { key: "unit_cost_zar", header: "Unit Cost" },
  { key: "actions", header: "" },
] as const;

type AdjustmentLinesTableProps = {
  lines: AdjustmentLine[];
  locationId: string;
  inventory: InventorySku[];
  canMutate: boolean;
  busy: boolean;
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

export function lineNewQty(line: AdjustmentLine, currentQty: number): number {
  if (typeof line.new_qty === "number") {
    return line.new_qty;
  }
  return currentQty + line.qty_delta;
}

function formatDelta(delta: number): string {
  if (delta > 0) {
    return `+${delta}`;
  }
  return String(delta);
}

function formatCost(value: string | null): string {
  if (!value) {
    return "—";
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }
  return formatPriceAmount(parsed);
}

export function AdjustmentLinesTable({
  lines,
  locationId,
  inventory,
  canMutate,
  busy,
  onRemove,
}: AdjustmentLinesTableProps) {
  const showActions = Boolean(canMutate && onRemove);
  const headers = useMemo(
    () => (showActions ? [...LINE_HEADERS] : LINE_HEADERS.filter((header) => header.key !== "actions")),
    [showActions],
  );
  const rows = useMemo(
    () =>
      lines.map((line) => {
        const currentQty = lineCurrentQty(line, inventory, locationId);
        return {
          id: line.id,
          product: line.id,
          current_qty: String(currentQty),
          qty_delta: formatDelta(line.qty_delta),
          new_qty: String(lineNewQty(line, currentQty)),
          unit_cost_zar: formatCost(line.unit_cost_zar),
          actions: line.id,
        };
      }),
    [inventory, lines, locationId],
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
        </TableContainer>
      )}
    </DataTable>
  );
}

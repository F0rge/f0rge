"use client";

import {
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
import { useMemo } from "react";

import type { StocktakeLine } from "@/lib/api";

export type DraftQty = number | "";

const LINE_HEADERS = [
  { key: "our_ref", header: "Our ref" },
  { key: "name", header: "Name" },
  { key: "our_barcode", header: "Our barcode" },
  { key: "expected_qty", header: "Expected" },
  { key: "counted_qty", header: "Counted" },
  { key: "variance", header: "Variance" },
] as const;

type StocktakeLinesTableProps = {
  lines: StocktakeLine[];
  drafts: Record<string, DraftQty>;
  highlightedLineId: string | null;
  canMutate: boolean;
  busy: boolean;
  onDraftChange: (lineId: string, value: DraftQty) => void;
  onCountedBlur: (lineId: string) => void;
};

function varianceOf(expected: number, counted: DraftQty): number | null {
  return counted === "" ? null : counted - expected;
}

function formatVariance(variance: number | null): string {
  if (variance === null) {
    return "—";
  }
  if (variance > 0) {
    return `+${variance}`;
  }
  return String(variance);
}

function varianceColor(variance: number | null): string | undefined {
  if (variance === null) {
    return undefined;
  }
  if (variance === 0) {
    return "var(--cds-support-success, #24a148)";
  }
  if (variance < 0) {
    return "var(--cds-support-error, #da1e28)";
  }
  return "var(--cds-link-primary, #0f62fe)";
}

export function StocktakeLinesTable({
  lines,
  drafts,
  highlightedLineId,
  canMutate,
  busy,
  onDraftChange,
  onCountedBlur,
}: StocktakeLinesTableProps) {
  const countedCount = lines.filter((line) => drafts[line.id] !== "").length;
  const pendingCount = lines.length - countedCount;
  const rows = useMemo(
    () =>
      lines.map((line) => ({
        id: line.id,
        our_ref: line.our_ref,
        name: line.name,
        our_barcode: line.our_barcode,
        expected_qty: String(line.expected_qty),
        counted_qty: line.id,
        variance: line.id,
      })),
    [lines],
  );

  return (
    <DataTable rows={rows} headers={[...LINE_HEADERS]}>
      {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
        <TableContainer
          title="Inventory list"
          description={`${countedCount} counted, ${pendingCount} pending`}
        >
          <Table {...getTableProps()}>
            <TableHead>
              <TableRow>
                {headers.map((header) => (
                  <TableHeader {...getHeaderProps({ header })} key={header.key}>
                    {header.header}
                  </TableHeader>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {tableRows.map((row) => {
                const line = lines.find((entry) => entry.id === row.id);
                const draft = drafts[row.id] ?? "";
                const variance = line ? varianceOf(line.expected_qty, draft) : null;
                return (
                  <TableRow
                    {...getRowProps({ row })}
                    key={row.id}
                    style={
                      row.id === highlightedLineId
                        ? { backgroundColor: "var(--cds-highlight, #f2f8ff)" }
                        : undefined
                    }
                  >
                    {row.cells.map((cell) => {
                      if (cell.info.header === "counted_qty") {
                        return (
                          <TableCell key={cell.id}>
                            <div style={{ maxWidth: "6.5rem" }}>
                              <NumberInput
                                id={`stocktake-counted-${row.id}`}
                                label="Counted"
                                hideLabel
                                min={0}
                                step={1}
                                size="sm"
                                value={draft}
                                disabled={!canMutate || busy}
                                onChange={(_event, { value }) => {
                                  onDraftChange(row.id, value === "" ? "" : Number(value));
                                }}
                                onBlur={() => onCountedBlur(row.id)}
                              />
                            </div>
                          </TableCell>
                        );
                      }
                      if (cell.info.header === "variance") {
                        return (
                          <TableCell key={cell.id}>
                            <span style={{ color: varianceColor(variance), fontWeight: 600 }}>
                              {formatVariance(variance)}
                            </span>
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

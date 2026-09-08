"use client";

import {
  NumberInput,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
} from "@carbon/react";

import type { Location } from "@/lib/api";
import type { PickLine } from "@/lib/picks";

type PickMatrixProps = {
  locations: Location[];
  lines: PickLine[];
  onHand: Record<string, Record<string, number>>;
  qty: Record<string, Record<string, number>>;
  onQtyChange: (skuId: string, locationId: string, qty: number) => void;
  readOnly: boolean;
};

function cellOnHand(
  onHand: Record<string, Record<string, number>>,
  line: PickLine,
  locationId: string,
): number {
  const fromPreview = onHand[line.sku_id]?.[locationId];
  if (typeof fromPreview === "number") {
    return fromPreview;
  }
  return line.allocations.find((entry) => entry.location_id === locationId)?.on_hand ?? 0;
}

export function PickMatrix({
  locations,
  lines,
  onHand,
  qty,
  onQtyChange,
  readOnly,
}: PickMatrixProps) {
  return (
    <TableContainer className="vellano-pick-matrix">
      <Table size="sm">
        <TableHead>
          <TableRow>
            <TableHeader>Component</TableHeader>
            <TableHeader>Needed</TableHeader>
            {locations.map((location) => (
              <TableHeader key={location.id}>
                {location.name}
                <div className="vellano-muted-text">
                  {location.type === "warehouse" ? "Warehouse" : "Showroom"}
                </div>
              </TableHeader>
            ))}
            <TableHeader>Picked</TableHeader>
          </TableRow>
        </TableHead>
        <TableBody>
          {lines.map((line) => {
            const picked = locations.reduce(
              (sum, location) => sum + (qty[line.sku_id]?.[location.id] ?? 0),
              0,
            );
            return (
              <TableRow key={line.sku_id}>
                <TableCell>
                  <strong>{line.sku_our_ref || line.sku_id}</strong>
                  <div className="vellano-muted-text">{line.sku_name}</div>
                </TableCell>
                <TableCell>{line.qty_needed}</TableCell>
                {locations.map((location) => {
                  const available = cellOnHand(onHand, line, location.id);
                  const value = qty[line.sku_id]?.[location.id] ?? 0;
                  return (
                    <TableCell key={location.id}>
                      <div className="vellano-muted-text">On hand {available}</div>
                      <NumberInput
                        id={`pick-qty-${line.sku_id}-${location.id}`}
                        hideLabel
                        label={`Pick qty at ${location.name}`}
                        min={0}
                        max={available}
                        step={1}
                        value={value}
                        disabled={readOnly}
                        onChange={(_, { value: next }) => {
                          const parsed =
                            next === "" ? 0 : typeof next === "number" ? next : Number(next);
                          onQtyChange(
                            line.sku_id,
                            location.id,
                            Number.isFinite(parsed) ? Math.max(0, parsed) : 0,
                          );
                        }}
                      />
                    </TableCell>
                  );
                })}
                <TableCell>
                  {picked} / {line.qty_needed}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

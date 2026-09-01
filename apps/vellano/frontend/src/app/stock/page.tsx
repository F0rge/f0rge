"use client";

import {
  DataTable,
  InlineNotification,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
} from "@carbon/react";
import { useCallback, useEffect, useState } from "react";

import { canViewCostAudit, listInventory, type InventorySku } from "@/lib/api";
import { CostAuditPanel } from "@/components/cost-audit-panel";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "our_ref", header: "Our ref" },
  { key: "name", header: "Name" },
  { key: "on_order", header: "On order" },
  { key: "on_hand", header: "On hand" },
  { key: "sellable", header: "Sellable" },
  { key: "unit_cost_zar", header: "Unit cost ZAR" },
  { key: "locations", header: "Locations" },
] as const;

type StockRow = {
  id: string;
  our_ref: string;
  name: string;
  on_order: string;
  on_hand: string;
  sellable: string;
  unit_cost_zar: string;
  locations: string;
};

export default function StockPage() {
  const { user } = useAuth();
  const canViewCost = canViewCostAudit(user);
  const [inventory, setInventory] = useState<InventorySku[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadInventory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listInventory();
      setInventory(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load inventory.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadInventory();
    }
  }, [user, loadInventory]);

  const tableHeaders = canViewCost
    ? TABLE_HEADERS
    : TABLE_HEADERS.filter((header) => header.key !== "unit_cost_zar");

  const rows: StockRow[] = inventory.map((entry) => ({
    id: entry.sku_id,
    our_ref: entry.our_ref,
    name: entry.name,
    on_order: String(entry.on_order),
    on_hand: String(entry.on_hand),
    sellable: entry.sellable ? "Yes" : "No",
    unit_cost_zar: canViewCost ? (entry.unit_cost_zar ?? "—") : "—",
    locations: entry.sku_id,
  }));

  return (
    <Stack gap={6}>
      <div>
        <h1 className="cds--type-productive-heading-04">Stock</h1>
        <p className="cds--type-body-01">
          Inventory on order and on hand. On-order stock is not sellable until received.
        </p>
      </div>

      {error ? (
        <InlineNotification
          kind="error"
          title="Error"
          subtitle={error}
          onCloseButtonClick={() => setError(null)}
          lowContrast
        />
      ) : null}

      {loading ? (
        <p className="cds--type-body-01">Loading stock…</p>
      ) : inventory.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No stock"
          subtitle="No inventory records yet. Raise a PO and mark on water to see on-order quantities."
          hideCloseButton
          lowContrast
        />
      ) : (
        <DataTable rows={rows} headers={[...tableHeaders]}>
          {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Stock" description="All inventory SKUs">
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
                    const entry = inventory.find((item) => item.sku_id === row.id);
                    return (
                      <TableRow {...getRowProps({ row })} key={row.id}>
                        {row.cells.map((cell) => {
                          if (cell.info.header === "locations" && entry) {
                            if (entry.locations.length === 0) {
                              return <TableCell key={cell.id}>—</TableCell>;
                            }
                            return (
                              <TableCell key={cell.id}>
                                {entry.locations.map((loc) => {
                                  const bins = loc.bins ?? [];
                                  return (
                                    <div key={loc.location_id}>
                                      <div>
                                        {loc.location_name}: {loc.on_hand}
                                        {canViewCost && loc.unit_cost_zar
                                          ? ` @ ${loc.unit_cost_zar} ZAR`
                                          : ""}
                                      </div>
                                      {bins.length > 0 ? (
                                        <div className="cds--type-label-01 vellano-muted-text">
                                          {bins
                                            .map((bin) => `${bin.code}: ${bin.on_hand}`)
                                            .join(" · ")}
                                        </div>
                                      ) : null}
                                    </div>
                                  );
                                })}
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
      )}

      <CostAuditPanel
        skuOptions={inventory.map((entry) => ({
          id: entry.sku_id,
          label: `${entry.our_ref} — ${entry.name}`,
        }))}
      />
    </Stack>
  );
}

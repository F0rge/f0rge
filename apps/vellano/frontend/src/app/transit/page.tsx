"use client";

import {
  Button,
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
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  PO_STATUS_LABELS,
  listInventory,
  listPurchaseOrders,
  type InventorySku,
  type PurchaseOrder,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "po_number", header: "PO number" },
  { key: "supplier_name", header: "Supplier" },
  { key: "status", header: "Status" },
  { key: "line_count", header: "Lines" },
  { key: "actions", header: "" },
] as const;

type TransitRow = {
  id: string;
  po_number: string;
  supplier_name: string;
  status: string;
  line_count: string;
  actions: string;
};

export default function TransitPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [inventory, setInventory] = useState<InventorySku[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [orderData, inventoryData] = await Promise.all([
        listPurchaseOrders(),
        listInventory(),
      ]);
      setOrders(
        orderData.filter((entry) => entry.status === "on_water" || entry.status === "landed"),
      );
      setInventory(inventoryData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load transit data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadData();
    }
  }, [user, loadData]);

  const onOrderSkus = useMemo(
    () => inventory.filter((entry) => entry.on_order > 0),
    [inventory],
  );

  const rows: TransitRow[] = orders.map((entry) => ({
    id: entry.id,
    po_number: entry.po_number,
    supplier_name: entry.supplier_name,
    status: PO_STATUS_LABELS[entry.status],
    line_count: String(entry.lines.length),
    actions: entry.id,
  }));

  return (
    <Stack gap={6}>
      <div>
        <h1 className="cds--type-productive-heading-04">Transit</h1>
        <p className="cds--type-body-01">
          Purchase orders on water or landed, awaiting receive. On-order stock is not sellable.
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
        <p className="cds--type-body-01">Loading transit…</p>
      ) : orders.length === 0 ? (
        <InlineNotification
          kind="info"
          title="Nothing in transit"
          subtitle="No purchase orders are currently on water or landed."
          hideCloseButton
          lowContrast
        />
      ) : (
        <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
          {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="In transit" description="POs on water or landed">
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
                  {tableRows.map((row) => (
                    <TableRow {...getRowProps({ row })} key={row.id}>
                      {row.cells.map((cell) => {
                        if (cell.info.header === "actions") {
                          return (
                            <TableCell key={cell.id}>
                              <Button
                                kind="ghost"
                                size="sm"
                                onClick={() => router.push(`/purchase-orders/${row.id}`)}
                              >
                                Open PO
                              </Button>
                            </TableCell>
                          );
                        }
                        return <TableCell key={cell.id}>{cell.value}</TableCell>;
                      })}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </DataTable>
      )}

      <div>
        <h2 className="cds--type-productive-heading-03">On-order inventory</h2>
        {loading ? null : onOrderSkus.length === 0 ? (
          <p className="cds--type-body-01">No SKUs currently on order.</p>
        ) : (
          <TableContainer title="On order" description="Stock in transit — not sellable until received">
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeader>Our ref</TableHeader>
                  <TableHeader>Name</TableHeader>
                  <TableHeader>On order</TableHeader>
                  <TableHeader>On hand</TableHeader>
                  <TableHeader>Sellable</TableHeader>
                </TableRow>
              </TableHead>
              <TableBody>
                {onOrderSkus.map((entry) => (
                  <TableRow key={entry.sku_id}>
                    <TableCell>{entry.our_ref}</TableCell>
                    <TableCell>{entry.name}</TableCell>
                    <TableCell>{entry.on_order}</TableCell>
                    <TableCell>{entry.on_hand}</TableCell>
                    <TableCell>{entry.sellable ? "Yes" : "Not sellable"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </div>
    </Stack>
  );
}

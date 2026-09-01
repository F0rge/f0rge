"use client";

import {
  Button,
  Checkbox,
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
  ApiError,
  canRaisePo,
  createReorderDraftPo,
  formatZarAmount,
  listReorder,
  type PurchaseOrder,
  type ReorderRow,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "select", header: "" },
  { key: "our_ref", header: "Our ref" },
  { key: "name", header: "Name" },
  { key: "on_hand", header: "On hand" },
  { key: "on_order", header: "On order" },
  { key: "reorder_min", header: "Reorder min" },
  { key: "suggested_qty", header: "Suggested qty" },
  { key: "preferred_supplier", header: "Preferred supplier" },
  { key: "last_landed", header: "Last landed" },
] as const;

type ReorderTableRow = {
  id: string;
  select: string;
  our_ref: string;
  name: string;
  on_hand: string;
  on_order: string;
  reorder_min: string;
  suggested_qty: string;
  preferred_supplier: string;
  last_landed: string;
};

export default function ReorderPage() {
  const router = useRouter();
  const { user } = useAuth();
  const canRaise = canRaisePo(user?.role);
  const [rows, setRows] = useState<ReorderRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [createdPos, setCreatedPos] = useState<PurchaseOrder[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());
  const [creating, setCreating] = useState(false);

  const loadRows = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listReorder();
      setRows(data);
      setSelectedIds((prev) => {
        const valid = new Set(data.map((entry) => entry.sku_id));
        const next = new Set<string>();
        for (const id of prev) {
          if (valid.has(id)) {
            next.add(id);
          }
        }
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load reorder list.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadRows();
    }
  }, [user, loadRows]);

  const rowById = useMemo(() => {
    const map: Record<string, ReorderRow> = {};
    for (const entry of rows) {
      map[entry.sku_id] = entry;
    }
    return map;
  }, [rows]);

  const allSelected = rows.length > 0 && rows.every((entry) => selectedIds.has(entry.sku_id));

  const selectedRows = rows.filter((entry) => selectedIds.has(entry.sku_id));
  const missingSupplier = selectedRows.some((entry) => !entry.preferred_supplier_id);

  const tableRows: ReorderTableRow[] = rows.map((entry) => ({
    id: entry.sku_id,
    select: entry.sku_id,
    our_ref: entry.our_ref,
    name: entry.name,
    on_hand: String(entry.on_hand),
    on_order: String(entry.on_order),
    reorder_min: String(entry.reorder_min),
    suggested_qty: String(entry.suggested_qty),
    preferred_supplier: entry.preferred_supplier_name?.trim() || "—",
    last_landed: entry.last_landed_cost_zar
      ? formatZarAmount(entry.last_landed_cost_zar)
      : "—",
  }));

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function toggleSelectAll() {
    if (allSelected) {
      setSelectedIds(new Set());
      return;
    }
    setSelectedIds(new Set(rows.map((entry) => entry.sku_id)));
  }

  async function handleCreateDraftPo() {
    if (!canRaise || selectedIds.size === 0 || missingSupplier) {
      return;
    }
    setCreating(true);
    setError(null);
    setSuccess(null);
    setCreatedPos([]);
    try {
      const result = await createReorderDraftPo([...selectedIds]);
      const poNumbers = result.purchase_orders.map((entry) => entry.po_number).join(", ");
      setSuccess(`Created draft PO${result.purchase_orders.length === 1 ? "" : "s"}: ${poNumbers}`);
      setCreatedPos(result.purchase_orders);
      setSelectedIds(new Set());
      await loadRows();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Failed to create draft purchase orders.");
      }
    } finally {
      setCreating(false);
    }
  }

  const createDisabled =
    !canRaise || selectedIds.size === 0 || missingSupplier || creating;

  const tableHeaders = canRaise
    ? TABLE_HEADERS
    : TABLE_HEADERS.filter((header) => header.key !== "select");

  return (
    <Stack gap={6}>
      <div className="vellano-page-header">
        <div>
          <h1 className="cds--type-productive-heading-04">Reorder</h1>
          <p className="cds--type-body-01">
            SKUs below minimum stock. Create draft purchase orders to preferred suppliers.
          </p>
        </div>
        {canRaise ? (
          <Button disabled={createDisabled} onClick={() => void handleCreateDraftPo()}>
            {creating ? "Creating…" : "Create draft PO"}
          </Button>
        ) : null}
      </div>

      {success ? (
        <Stack gap={3}>
          <InlineNotification
            kind="success"
            title="Draft purchase orders created"
            subtitle={success}
            onCloseButtonClick={() => {
              setSuccess(null);
              setCreatedPos([]);
            }}
            lowContrast
          />
          {createdPos.length > 0 ? (
            <Button kind="ghost" onClick={() => router.push("/purchase-orders")}>
              View purchase orders
            </Button>
          ) : null}
        </Stack>
      ) : null}

      {error ? (
        <InlineNotification
          kind="error"
          title="Error"
          subtitle={error}
          onCloseButtonClick={() => setError(null)}
          lowContrast
        />
      ) : null}

      {canRaise && selectedIds.size > 0 && missingSupplier ? (
        <InlineNotification
          kind="warning"
          title="Preferred supplier required"
          subtitle="Every selected SKU needs a preferred supplier before creating draft POs."
          hideCloseButton
          lowContrast
        />
      ) : null}

      {loading ? (
        <p className="cds--type-body-01">Loading reorder list…</p>
      ) : rows.length === 0 ? (
        <InlineNotification
          kind="info"
          title="Nothing to reorder"
          subtitle="No SKUs are below their reorder minimum."
          hideCloseButton
          lowContrast
        />
      ) : (
        <DataTable rows={tableRows} headers={[...tableHeaders]}>
          {({ rows: dataRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer
              title="Reorder list"
              description="SKUs below minimum stock with suggested order quantities"
            >
              <Table {...getTableProps()}>
                <TableHead>
                  <TableRow>
                    {headers.map((header) => (
                      <TableHeader {...getHeaderProps({ header })} key={header.key}>
                        {header.key === "select" && canRaise ? (
                          <Checkbox
                            id="reorder-select-all"
                            labelText="Select all"
                            hideLabel
                            checked={allSelected}
                            indeterminate={
                              !allSelected && rows.some((entry) => selectedIds.has(entry.sku_id))
                            }
                            onChange={() => toggleSelectAll()}
                          />
                        ) : (
                          header.header
                        )}
                      </TableHeader>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {dataRows.map((row) => {
                    const entry = rowById[row.id];
                    return (
                      <TableRow {...getRowProps({ row })} key={row.id}>
                        {row.cells.map((cell) => {
                          if (cell.info.header === "select" && canRaise && entry) {
                            return (
                              <TableCell key={cell.id}>
                                <Checkbox
                                  id={`reorder-select-${entry.sku_id}`}
                                  labelText={`Select ${entry.our_ref}`}
                                  hideLabel
                                  checked={selectedIds.has(entry.sku_id)}
                                  onChange={() => toggleSelect(entry.sku_id)}
                                />
                              </TableCell>
                            );
                          }
                          if (
                            cell.info.header === "on_hand" ||
                            cell.info.header === "on_order" ||
                            cell.info.header === "reorder_min" ||
                            cell.info.header === "suggested_qty" ||
                            cell.info.header === "last_landed"
                          ) {
                            return (
                              <TableCell key={cell.id} style={{ textAlign: "right" }}>
                                {cell.value}
                              </TableCell>
                            );
                          }
                          if (cell.info.header === "select" && !canRaise) {
                            return <TableCell key={cell.id} />;
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
    </Stack>
  );
}

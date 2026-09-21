"use client";

import {
  Button,
  DataTable,
  InlineNotification,
  Modal,
  Pagination,
  Select,
  SelectItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  TextInput,
} from "@carbon/react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  canMutateOrders,
  cancelSalesOrder,
  confirmSalesOrder,
  createPick,
  formatZarAmount,
  getSalesOrder,
  isActiveLocation,
  listLocations,
  listSalesOrders,
  remainderInvoiceSalesOrder,
  type Location,
  type SalesOrderListItem,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "so_number", header: "Reference" },
  { key: "customer_name", header: "Customer" },
  { key: "items", header: "Items" },
  { key: "total_inc_vat", header: "Total" },
  { key: "amount_paid", header: "Paid" },
  { key: "balance", header: "Balance" },
  { key: "status", header: "Status" },
  { key: "actions", header: "Action" },
] as const;

export default function OrdersPage() {
  const { user } = useAuth();
  const canMutate = canMutateOrders(user);
  const [orders, setOrders] = useState<SalesOrderListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [locations, setLocations] = useState<Location[]>([]);
  const [confirmRow, setConfirmRow] = useState<SalesOrderListItem | null>(null);
  const [locationId, setLocationId] = useState("");
  const [holdStock, setHoldStock] = useState(true);
  const [depositAmount, setDepositAmount] = useState("");

  const loadOrders = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const pageData = await listSalesOrders({ limit: pageSize, offset: (page - 1) * pageSize });
      setOrders(pageData.items);
      setTotal(pageData.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load orders");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  const loadOrderForm = useCallback(async () => {
    try {
      const locationRows = await listLocations();
      setLocations(locationRows.filter(isActiveLocation));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load locations");
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadOrders();
    }
  }, [user, loadOrders]);

  useEffect(() => {
    if (user && confirmRow) {
      void loadOrderForm();
    }
  }, [user, confirmRow, loadOrderForm]);

  const rows = useMemo(
    () =>
      orders.map((order) => ({
        id: order.id,
        so_number: order.so_number,
        customer_name: order.customer_name,
        items: order.items_label,
        total_inc_vat: formatZarAmount(order.total_inc_vat),
        amount_paid: formatZarAmount(order.amount_paid),
        balance: formatZarAmount(order.balance),
        status: order.status,
        actions: order.id,
      })),
    [orders],
  );

  return (
    <Stack gap={5}>
      {error ? <InlineNotification kind="error" title={error} hideCloseButton /> : null}
      <h1>Sales orders</h1>
      {loading ? <p className="cds--type-body-01">Loading orders…</p> : null}
      <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
        {({ rows: tableRows, headers, getHeaderProps, getRowProps, getTableProps }) => (
          <TableContainer>
            <Table {...getTableProps()}>
              <TableHead>
                <TableRow>
                  {headers.map((header) => {
                    const { key, ...rest } = getHeaderProps({ header });
                    return (
                      <TableHeader key={key} {...rest}>
                        {header.header}
                      </TableHeader>
                    );
                  })}
                </TableRow>
              </TableHead>
              <TableBody>
                {tableRows.map((row) => {
                  const order = orders.find((item) => item.id === row.id);
                  const { key, ...rowProps } = getRowProps({ row });
                  return (
                    <TableRow key={key} {...rowProps}>
                      {row.cells.map((cell) => (
                        <TableCell key={cell.id}>
                          {cell.info.header === "actions" && order && canMutate ? (
                            <Stack gap={2} orientation="horizontal">
                              {order.status === "draft" ? (
                                <Button size="sm" onClick={() => setConfirmRow(order)}>
                                  Confirm
                                </Button>
                              ) : null}
                              {order.status === "open" || order.status === "awaiting_stock" ? (
                                <>
                                  <Button
                                    size="sm"
                                    kind="secondary"
                                    onClick={() =>
                                      void getSalesOrder(order.id)
                                        .then(async (detail) => {
                                          for (const line of detail.lines) {
                                            try {
                                              await createPick({ sales_order_line_id: line.id });
                                            } catch (err) {
                                              if (
                                                !(err instanceof ApiError) ||
                                                !err.message.toLowerCase().includes("already")
                                              ) {
                                                throw err;
                                              }
                                            }
                                          }
                                          await loadOrders();
                                        })
                                        .catch((err) =>
                                          setError(
                                            err instanceof ApiError ? err.message : "Pick failed",
                                          ),
                                        )
                                    }
                                  >
                                    Create picks
                                  </Button>
                                  <Button
                                    size="sm"
                                    kind="tertiary"
                                    onClick={() =>
                                      void remainderInvoiceSalesOrder(order.id)
                                        .then(loadOrders)
                                        .catch((err) =>
                                          setError(err instanceof ApiError ? err.message : "Invoice failed"),
                                        )
                                    }
                                  >
                                    Remainder invoice
                                  </Button>
                                  <Button
                                    size="sm"
                                    kind="ghost"
                                    onClick={() =>
                                      void cancelSalesOrder(order.id)
                                        .then(loadOrders)
                                        .catch((err) =>
                                          setError(err instanceof ApiError ? err.message : "Cancel failed"),
                                        )
                                    }
                                  >
                                    Cancel
                                  </Button>
                                </>
                              ) : null}
                            </Stack>
                          ) : (
                            cell.value
                          )}
                        </TableCell>
                      ))}
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </DataTable>
      <Pagination
        page={page}
        pageSize={pageSize}
        pageSizes={[10, 25, 50]}
        totalItems={total}
        onChange={({ page: nextPage, pageSize: nextSize }) => {
          setPage(nextPage);
          setPageSize(nextSize);
        }}
      />
      <Modal
        open={Boolean(confirmRow)}
        modalHeading="Confirm sales order"
        primaryButtonText="Confirm"
        secondaryButtonText="Cancel"
        onRequestClose={() => setConfirmRow(null)}
        onRequestSubmit={() => {
          if (!confirmRow) {
            return;
          }
          void confirmSalesOrder(confirmRow.id, {
            location_id: locationId || undefined,
            hold_stock: holdStock && Boolean(locationId),
            deposit: depositAmount ? { amount: depositAmount, tender: "eft" } : undefined,
          })
            .then(() => {
              setConfirmRow(null);
              return loadOrders();
            })
            .catch((err) => setError(err instanceof ApiError ? err.message : "Confirm failed"));
        }}
      >
        <Stack gap={4}>
          <Select
            id="confirm-location"
            labelText="Hold location"
            value={locationId}
            onChange={(event) => setLocationId(event.target.value)}
          >
            <SelectItem value="" text="No hold" />
            {locations.map((location) => (
              <SelectItem key={location.id} value={location.id} text={`${location.name} (${location.type})`} />
            ))}
          </Select>
          <Select
            id="confirm-hold"
            labelText="Hold stock"
            value={holdStock ? "yes" : "no"}
            onChange={(event) => setHoldStock(event.target.value === "yes")}
          >
            <SelectItem value="yes" text="Yes" />
            <SelectItem value="no" text="No" />
          </Select>
          <TextInput
            id="confirm-deposit"
            labelText="Deposit (optional)"
            value={depositAmount}
            onChange={(event) => setDepositAmount(event.target.value)}
          />
        </Stack>
      </Modal>
    </Stack>
  );
}

"use client";

import {
  Button,
  Checkbox,
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
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  ApiError,
  canMutateDeliveries,
  canMutateOrders,
  cancelSalesOrder,
  confirmSalesOrder,
  createPick,
  formatZarAmount,
  getSalesOrder,
  getStorefrontRefundStatus,
  isActiveLocation,
  listLocations,
  listStorefrontHandoffs,
  listSalesOrders,
  retryStorefrontHandoff,
  requestStorefrontRefund,
  updateStorefrontCollectionStatus,
  remainderInvoiceSalesOrder,
  type Location,
  type SalesOrderListItem,
  type StorefrontRefund,
  type StorefrontHandoff,
  type StorefrontRefundStatus,
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

function zarToMinorUnits(value: string): number | null {
  const normalized = value.trim();
  const match = /^(0|[1-9]\d*)(?:\.(\d{1,2}))?$/.exec(normalized);
  if (!match) return null;
  const whole = Number(match[1]);
  const cents = Number((match[2] || "").padEnd(2, "0"));
  const minor = whole * 100 + cents;
  return Number.isSafeInteger(minor) ? minor : null;
}

function selectedLineRefund(status: StorefrontRefundStatus, quantities: Record<string, string>): {
  valid: boolean;
  lines: { external_line_id: string; quantity: number }[];
  amountMinor: number;
} {
  const lines: { external_line_id: string; quantity: number }[] = [];
  let amountMinor = 0;
  for (const balance of status.line_balances) {
    const rawQuantity = quantities[balance.external_line_id] || "";
    if (!rawQuantity) continue;
    if (!/^[1-9]\d*$/.test(rawQuantity)) return { valid: false, lines: [], amountMinor: 0 };
    const quantity = Number(rawQuantity);
    if (!Number.isSafeInteger(quantity) || quantity > balance.remaining_quantity || balance.remaining_quantity <= 0) {
      return { valid: false, lines: [], amountMinor: 0 };
    }
    const base = Math.floor(balance.remaining_amount_minor / balance.remaining_quantity);
    const remainder = balance.remaining_amount_minor % balance.remaining_quantity;
    amountMinor += base * quantity + Math.min(quantity, remainder);
    lines.push({ external_line_id: balance.external_line_id, quantity });
  }
  return { valid: lines.length > 0 && Number.isSafeInteger(amountMinor) && amountMinor > 0, lines, amountMinor };
}

export default function OrdersPage() {
  const { user } = useAuth();
  const canMutate = canMutateOrders(user);
  const canRefund = user?.permissions.includes("sales.refunds") === true;
  const canCollect = canMutateDeliveries(user);
  const canReadHandoffs = canMutate || canRefund || canCollect;
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
  const [handoffs, setHandoffs] = useState<StorefrontHandoff[]>([]);
  const [retryingHandoffId, setRetryingHandoffId] = useState<string | null>(null);
  const [collectingHandoffId, setCollectingHandoffId] = useState<string | null>(null);
  const [refundHandoff, setRefundHandoff] = useState<StorefrontHandoff | null>(null);
  const [refundStatus, setRefundStatus] = useState<StorefrontRefundStatus | null>(null);
  const [refundMethod, setRefundMethod] = useState<"amount" | "lines">("amount");
  const [refundAmount, setRefundAmount] = useState("");
  const [refundLineQuantities, setRefundLineQuantities] = useState<Record<string, string>>({});
  const [refundCancelOrder, setRefundCancelOrder] = useState(false);
  const [refundSaving, setRefundSaving] = useState(false);
  const [refundIdempotencyKey, setRefundIdempotencyKey] = useState("");
  const [refundError, setRefundError] = useState<string | null>(null);
  const refundViewSequence = useRef(0);
  const activeRefundHandoffId = useRef<string | null>(null);

  const loadOrders = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (canMutate) {
        const pageData = await listSalesOrders({ limit: pageSize, offset: (page - 1) * pageSize });
        setOrders(pageData.items);
        setTotal(pageData.total);
      } else {
        setOrders([]);
        setTotal(0);
      }
      if (canReadHandoffs) {
        const handoffData = await listStorefrontHandoffs();
        setHandoffs(handoffData.items);
      } else setHandoffs([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load orders");
    } finally {
      setLoading(false);
    }
  }, [canMutate, canReadHandoffs, page, pageSize]);

  const openRefund = (handoff: StorefrontHandoff) => {
    const sequence = ++refundViewSequence.current;
    activeRefundHandoffId.current = handoff.id;
    setRefundHandoff(handoff);
    setRefundAmount("");
    setRefundLineQuantities({});
    setRefundMethod("amount");
    setRefundCancelOrder(false);
    setRefundStatus(null);
    setRefundError(null);
    setRefundIdempotencyKey(crypto.randomUUID());
    void getStorefrontRefundStatus(handoff.id)
      .then((status) => {
        if (refundViewSequence.current === sequence && activeRefundHandoffId.current === handoff.id) {
          setRefundStatus(status);
        }
      })
      .catch((err) => {
        if (refundViewSequence.current === sequence && activeRefundHandoffId.current === handoff.id) {
          setRefundError(err instanceof Error ? err.message : "Could not load refund balance");
        }
      });
  };

  const closeRefund = () => {
    refundViewSequence.current += 1;
    activeRefundHandoffId.current = null;
    setRefundHandoff(null);
    setRefundStatus(null);
    setRefundError(null);
  };

  const submitRefund = async () => {
    if (!refundHandoff || !refundStatus) return;
    const handoffId = refundHandoff.id;
    const sequence = refundViewSequence.current;
    const isCurrentView = () => refundViewSequence.current === sequence && activeRefundHandoffId.current === handoffId;
    const lineRefund = selectedLineRefund(refundStatus, refundLineQuantities);
    const amountMinor = refundMethod === "amount" ? zarToMinorUnits(refundAmount) : lineRefund.amountMinor;
    const refundLimit = refundStatus.invoice_id
      ? refundStatus.invoice_refund_available_minor
      : refundStatus.available_refund_minor;
    if (amountMinor === null || amountMinor <= 0 || amountMinor > refundLimit ||
      (refundStatus.invoice_id && (!refundStatus.invoice_refund_eligible || refundMethod !== "amount" || refundCancelOrder)) ||
      (refundCancelOrder && amountMinor !== refundStatus.available_refund_minor) ||
      (refundMethod === "lines" && !lineRefund.valid)) return;
    setRefundSaving(true);
    setRefundError(null);
    try {
      const request = {
        idempotency_key: refundIdempotencyKey,
        cancel_order: refundCancelOrder,
        ...(refundMethod === "amount" ? { amount_minor: amountMinor } : { selected_lines: lineRefund.lines }),
      };
      let result: StorefrontRefund;
      try {
        result = await requestStorefrontRefund(handoffId, request);
      } catch (err) {
        if (isCurrentView()) {
          setRefundError(err instanceof ApiError ? err.message : "Refund request could not be submitted");
        }
        return;
      }
      if (!isCurrentView()) return;

      let status: StorefrontRefundStatus;
      try {
        status = await getStorefrontRefundStatus(handoffId);
      } catch {
        if (isCurrentView()) {
          setRefundStatus((current) => current ? {
            ...current,
            items: current.items.some((item) => item.id === result.id) ? current.items : [...current.items, result],
          } : current);
          setRefundError("Refund request was accepted, but its balance could not be refreshed. Reopen this handoff to reload its status. The current request key keeps a repeat submission of the same details idempotent.");
        }
        return;
      }
      if (!isCurrentView()) return;
      setRefundStatus({ ...status, items: status.items.some((item) => item.id === result.id)
        ? status.items : [...status.items, result] });
      setRefundAmount("");
      setRefundLineQuantities({});
      setRefundIdempotencyKey(crypto.randomUUID());
    } catch (err) {
      if (isCurrentView()) {
        setRefundError(err instanceof ApiError ? err.message : "Refund request could not be submitted");
      }
    } finally {
      setRefundSaving(false);
    }
  };

  const refundAmountMinor = zarToMinorUnits(refundAmount);
  const availableRefundMinor = refundStatus?.available_refund_minor ?? 0;
  const refundLimitMinor = refundStatus?.invoice_id
    ? refundStatus.invoice_refund_available_minor
    : availableRefundMinor;
  const selectedRefund = refundStatus ? selectedLineRefund(refundStatus, refundLineQuantities) : null;
  const selectedAmountMinor = refundMethod === "amount" ? refundAmountMinor : selectedRefund?.amountMinor ?? null;
  const refundFormValid = Boolean(refundStatus) && selectedAmountMinor !== null && selectedAmountMinor > 0 &&
    selectedAmountMinor <= refundLimitMinor &&
    (!refundStatus?.invoice_id || (refundStatus.invoice_refund_eligible && refundMethod === "amount" && !refundCancelOrder)) &&
    (!refundCancelOrder || selectedAmountMinor === availableRefundMinor) &&
    (refundMethod !== "lines" || selectedRefund?.valid === true);

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
      <h1>{canMutate ? "Sales orders" : canCollect ? "Storefront collection" : "Storefront refunds"}</h1>
      {canReadHandoffs ? (
        <section aria-labelledby="storefront-handoffs-heading">
          <Stack gap={3}>
            <h2 id="storefront-handoffs-heading">Storefront handoffs</h2>
            {handoffs.length === 0 ? <p>No Storefront handoffs recorded.</p> : null}
            {handoffs.map((handoff) => (
              <Stack
                key={handoff.id}
                gap={2}
                orientation="horizontal"
                className="storefront-handoff-row"
              >
                <span>
                  {handoff.external_order_id} · {handoff.status} · {handoff.fulfillment_type} · {handoff.fulfillment_status} · received {new Date(handoff.created_at).toLocaleString()}
                  {handoff.failure_code ? ` · ${handoff.failure_code}` : ""}
                  {` · attempts ${handoff.attempt_count} · ${handoff.correlation_id}`}
                </span>
                {canMutate && handoff.status !== "imported" && handoff.status !== "processing" ? (
                  <Button
                    size="sm"
                    kind="secondary"
                    disabled={retryingHandoffId === handoff.id}
                    onClick={() => {
                      setRetryingHandoffId(handoff.id);
                      void retryStorefrontHandoff(handoff.id)
                        .then(async () => {
                          await loadOrders();
                        })
                        .catch((err) =>
                          setError(err instanceof ApiError ? err.message : "Storefront retry failed"),
                        )
                        .finally(() => setRetryingHandoffId(null));
                    }}
                  >
                    Retry
                  </Button>
                ) : null}
                {canCollect && handoff.status === "imported" && handoff.fulfillment_type === "collection" && handoff.fulfillment_status === "confirmed" ? (
                  <Button
                    size="sm"
                    kind="secondary"
                    disabled={collectingHandoffId === handoff.id}
                    onClick={() => {
                      setCollectingHandoffId(handoff.id);
                      void updateStorefrontCollectionStatus(handoff.id, "ready_for_collection")
                        .then(async () => {
                          await loadOrders();
                        })
                        .catch((err) =>
                          setError(err instanceof ApiError ? err.message : "Collection status could not be updated"),
                        )
                        .finally(() => setCollectingHandoffId(null));
                    }}
                  >
                    Ready for collection
                  </Button>
                ) : null}
                {canCollect && handoff.status === "imported" && handoff.fulfillment_type === "collection" && handoff.fulfillment_status === "ready_for_collection" ? (
                  <Button
                    size="sm"
                    kind="secondary"
                    disabled={collectingHandoffId === handoff.id}
                    onClick={() => {
                      setCollectingHandoffId(handoff.id);
                      void updateStorefrontCollectionStatus(handoff.id, "collected")
                        .then(async () => {
                          await loadOrders();
                        })
                        .catch((err) =>
                          setError(err instanceof ApiError ? err.message : "Collection status could not be updated"),
                        )
                        .finally(() => setCollectingHandoffId(null));
                    }}
                  >
                    Collected
                  </Button>
                ) : null}
                {canRefund && handoff.status === "imported" ? (
                  <Button size="sm" kind="secondary" onClick={() => openRefund(handoff)}>
                    Refund
                  </Button>
                ) : null}
              </Stack>
            ))}
          </Stack>
        </section>
      ) : null}
      {loading ? <p className="cds--type-body-01">Loading orders…</p> : null}
      {canMutate ? <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
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
      : null}
      {canMutate ? <Pagination
        page={page}
        pageSize={pageSize}
        pageSizes={[10, 25, 50]}
        totalItems={total}
        onChange={({ page: nextPage, pageSize: nextSize }) => {
          setPage(nextPage);
          setPageSize(nextSize);
        }}
      /> : null}
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
      <Modal
        open={Boolean(refundHandoff)}
        modalHeading={`Storefront refund${refundHandoff ? ` · ${refundHandoff.external_order_id}` : ""}`}
        primaryButtonText={refundSaving ? "Submitting…" : "Request refund"}
        secondaryButtonText="Close"
        primaryButtonDisabled={refundSaving || !refundFormValid}
        onRequestClose={closeRefund}
        onRequestSubmit={() => void submitRefund()}
      >
        <Stack gap={4}>
          {refundError ? <InlineNotification kind="error" title={refundError} hideCloseButton /> : null}
          {!refundStatus && !refundError ? <p role="status">Loading captured and reserved refund balance…</p> : null}
          {refundStatus ? <>
            <p>Captured: {formatZarAmount((refundStatus.captured_amount_minor / 100).toFixed(2))}</p>
            <p>Already refunded: {formatZarAmount((refundStatus.confirmed_refund_minor / 100).toFixed(2))}</p>
            <p>Reserved or unresolved: {formatZarAmount((refundStatus.reserved_refund_minor / 100).toFixed(2))}</p>
            <p>Available to request: {formatZarAmount((availableRefundMinor / 100).toFixed(2))}</p>
            {refundStatus.invoice_id ? <p>Accepted-return credit available: {formatZarAmount((refundStatus.invoice_refund_available_minor / 100).toFixed(2))}</p> : null}
            {refundStatus.invoice_id ? <InlineNotification
              kind={refundStatus.invoice_refund_eligible ? "warning" : "error"}
              title={refundStatus.invoice_refund_eligible ? "Refund after accepted return" : "No eligible return credit"}
              subtitle={refundStatus.invoice_refund_eligible
                ? "Only an amount refund backed by a completed accepted return credit note is available. This does not cancel the order or restock items."
                : "An invoiced refund requires a completed accepted return and credit note. No automatic refund can be requested yet."}
              hideCloseButton
            /> : null}
            {!refundStatus.invoice_id ? <Select
              id="storefront-refund-method"
              labelText="Refund selection"
              value={refundMethod}
              onChange={(event) => {
                setRefundMethod(event.target.value === "lines" ? "lines" : "amount");
                setRefundAmount("");
                setRefundLineQuantities({});
              }}
            >
              <SelectItem value="amount" text="Enter an amount" />
              <SelectItem value="lines" text="Select item quantities" />
            </Select> : null}
            {refundMethod === "amount" ? <TextInput
              id="storefront-refund-amount"
              labelText="Refund amount (ZAR)"
              placeholder="0.00"
              value={refundAmount}
              onChange={(event) => setRefundAmount(event.target.value)}
              helperText={refundStatus.invoice_id
                ? `Enter an amount up to the completed return credit balance of ${formatZarAmount((refundLimitMinor / 100).toFixed(2))}. Pending and unknown refunds reserve the balance.`
                : "Enter a positive amount with up to two decimal places. Pending and unknown refunds reserve the balance."}
            /> : <Stack gap={3}>
              {refundStatus.line_balances.map((line) => <Stack key={line.external_line_id} gap={1}>
                <p>{line.title}{line.sku ? ` · ${line.sku}` : ""}</p>
                <p>Remaining: {line.remaining_quantity} of {line.original_quantity} · {formatZarAmount((line.remaining_amount_minor / 100).toFixed(2))}</p>
                <TextInput
                  id={`storefront-refund-line-${line.external_line_id}`}
                  type="number"
                  min={0}
                  max={line.remaining_quantity}
                  step={1}
                  labelText={`Quantity to refund · ${line.title}`}
                  value={refundLineQuantities[line.external_line_id] || ""}
                  onChange={(event) => setRefundLineQuantities((current) => ({
                    ...current,
                    [line.external_line_id]: event.target.value,
                  }))}
                />
              </Stack>)}
              {selectedRefund?.valid ? <p>Selected item refund: {formatZarAmount((selectedRefund.amountMinor / 100).toFixed(2))}</p> : null}
              {refundStatus.line_balances.length === 0 ? <p>No refundable item quantities remain.</p> : null}
              <p>Selected quantity is priced from the original captured item snapshot and remaining line balance. Use amount selection for delivery charges.</p>
            </Stack>}
            {!refundStatus.invoice_id ? <Checkbox
              id="storefront-refund-cancel-order"
              labelText="Also request eligible order cancellation"
              checked={refundCancelOrder}
              onChange={(_, { checked }) => setRefundCancelOrder(checked)}
            /> : null}
            {!refundStatus.invoice_id && refundCancelOrder ? <p>Cancellation requires refunding the full remaining balance. Stock is released only after Firstout confirms the physical cancellation separately.</p> : null}
            <div aria-live="polite">
              {refundStatus.items.map((item) => <p key={item.id}>
                {formatZarAmount((item.amount_minor / 100).toFixed(2))} · {item.status}
                {item.provider_result_code ? ` · Peach ${item.provider_result_code}` : ""}
              </p>)}
            </div>
          </> : null}
        </Stack>
      </Modal>
    </Stack>
  );
}

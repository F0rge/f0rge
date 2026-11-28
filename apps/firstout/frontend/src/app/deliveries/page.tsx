"use client";

import { ErrorNotice } from "@/components/error-notice";
import { PageLoading } from "@/components/page-loading";
import { ServerSearchComboBox } from "@/components/server-search-combo-box";
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
  Tag,
  TextArea,
} from "@carbon/react";
import { useRouter, useSearchParams } from "next/navigation";
import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";

import {
  ApiError,
  cancelDelivery,
  canMutateDeliveries,
  completeDelivery,
  createDelivery,
  getDelivery,
  getInvoice,
  getLayby,
  getSalesOrder,
  isActiveLocation,
  isInvoiceFullyPaid,
  listDeliveries,
  listInvoices,
  listLaybys,
  listSalesOrders,
  loadDelivery,
  packDelivery,
  type Delivery,
  type DeliveryListItem,
  type DeliverySourceType,
  type DeliveryStatus,
  type Invoice,
  type Layby,
  type Location,
  type SalesOrder,
} from "@/lib/api";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { usePageError } from "@/hooks/use-page-error";
import { useAuth } from "@/lib/auth";
import { referenceQueries } from "@/lib/queries";

const TABLE_HEADERS = [
  { key: "delivery_number", header: "Delivery ID" },
  { key: "source", header: "Source" },
  { key: "customer_name", header: "Customer" },
  { key: "location_name", header: "Location" },
  { key: "status", header: "Status" },
  { key: "delivery_date", header: "Delivery date" },
  { key: "actions", header: "Actions" },
] as const;

type DeliveryRow = {
  id: string;
  delivery_number: string;
  source: string;
  customer_name: string;
  location_name: string;
  status: string;
  delivery_date: string;
  actions: string;
};

function formatDate(iso: string | null): string {
  if (!iso) {
    return "—";
  }
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-ZA");
}

function statusLabel(status: DeliveryStatus): string {
  if (status === "draft") {
    return "Draft";
  }
  if (status === "packed") {
    return "Packed";
  }
  if (status === "loaded") {
    return "Loaded";
  }
  if (status === "delivered") {
    return "Delivered";
  }
  return "Cancelled";
}

function statusTagType(status: DeliveryStatus): "blue" | "teal" | "purple" | "green" | "gray" {
  if (status === "draft") {
    return "blue";
  }
  if (status === "packed") {
    return "teal";
  }
  if (status === "loaded") {
    return "purple";
  }
  if (status === "delivered") {
    return "green";
  }
  return "gray";
}

function sourceLabel(entry: DeliveryListItem): string {
  if (entry.source_type === "invoice") {
    return entry.invoice_number ?? "Invoice";
  }
  if (entry.source_type === "sales_order") {
    return entry.so_number ?? "Sales order";
  }
  return entry.layby_number ?? "Layby";
}

function defaultLocationId(locations: Location[]): string {
  const bedfordview = locations.find((entry) => entry.name.toLowerCase() === "bedfordview");
  return bedfordview?.id ?? locations[0]?.id ?? "";
}

function DeliveriesPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useAuth();
  const canMutate = canMutateDeliveries(user);
  const client = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedDelivery, setSelectedDelivery] = useState<Delivery | null>(null);
  const [saving, setSaving] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null);
  const [sourceType, setSourceType] = useState<DeliverySourceType>("invoice");
  const [invoiceId, setInvoiceId] = useState("");
  const [laybyId, setLaybyId] = useState("");
  const [salesOrderId, setSalesOrderId] = useState("");
  // null until staff pick one: the default dispatch location.
  const [locationChoice, setLocationId] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [sourceQuery, setSourceQuery] = useState("");
  const debouncedSourceQuery = useDebouncedValue(sourceQuery);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const prefillConsumed = useRef(false);

  const deliveriesQuery = useQuery({
    queryKey: ["deliveries", { page, pageSize }],
    queryFn: () => listDeliveries({ limit: pageSize, offset: (page - 1) * pageSize }),
    enabled: Boolean(user),
    placeholderData: keepPreviousData,
  });
  const deliveries = useMemo(() => deliveriesQuery.data?.items ?? [], [deliveriesQuery.data]);
  const total = deliveriesQuery.data?.total ?? 0;
  const loading = deliveriesQuery.isPending || deliveriesQuery.isFetching;

  const locationsQuery = useQuery({ ...referenceQueries.locations, enabled: createOpen && canMutate });
  const locations = useMemo(() => (locationsQuery.data ?? []).filter(isActiveLocation), [locationsQuery.data]);
  const locationId = locationChoice ?? defaultLocationId(locations);

  const optionsQuery = useQuery({
    queryKey: ["deliveries", "source-options", sourceType, debouncedSourceQuery],
    queryFn: async () => {
      const q = debouncedSourceQuery || undefined;
      if (sourceType === "invoice") {
        const data = await listInvoices({ limit: 25, q });
        return data.items.filter(isInvoiceFullyPaid).map((invoice) => ({
          id: invoice.id,
          label: `${invoice.invoice_number} — ${invoice.customer_name}`,
        }));
      }
      if (sourceType === "sales_order") {
        const data = await listSalesOrders({ limit: 25, q });
        return data.items
          .filter((entry) => entry.status !== "cancelled")
          .map((order) => ({ id: order.id, label: `${order.so_number} — ${order.customer_name}` }));
      }
      const data = await listLaybys({ limit: 25, q });
      return data.items
        .filter((entry) => entry.status !== "cancelled")
        .map((layby) => ({ id: layby.id, label: `${layby.layby_number} — ${layby.customer_name}` }));
    },
    enabled: createOpen && canMutate,
    // Keep the options (and the selection) while the next search runs, but never across source types.
    placeholderData: (previous, previousQuery) => (previousQuery?.queryKey[2] === sourceType ? previous : undefined),
  });
  const sourceOptions = optionsQuery.data ?? [];
  const invoiceOptions = sourceType === "invoice" ? sourceOptions : [];
  const salesOrderOptions = sourceType === "sales_order" ? sourceOptions : [];
  const laybyOptions = sourceType === "layby" ? sourceOptions : [];

  const sourceId = sourceType === "invoice" ? invoiceId : sourceType === "sales_order" ? salesOrderId : laybyId;
  const previewQuery = useQuery<Invoice | Layby | SalesOrder>({
    queryKey: ["deliveries", "source-preview", sourceType, sourceId],
    queryFn: () =>
      sourceType === "invoice" ? getInvoice(sourceId)
        : sourceType === "sales_order" ? getSalesOrder(sourceId)
          : getLayby(sourceId),
    enabled: Boolean(sourceId),
  });
  const sourcePreview = sourceId ? previewQuery.data ?? null : null;
  const sourceLoading = Boolean(sourceId) && previewQuery.isFetching;

  const loadFailure = deliveriesQuery.error ?? locationsQuery.error ?? optionsQuery.error ?? previewQuery.error;
  const { error, setError } = usePageError(loadFailure, "Failed to load deliveries.");
  const loadDeliveries = () => client.invalidateQueries({ queryKey: ["deliveries"] });

  useEffect(() => {
    if (!canMutate || prefillConsumed.current) {
      return;
    }
    const invoicePrefill = searchParams.get("invoice");
    const laybyPrefill = searchParams.get("layby");
    const orderPrefill = searchParams.get("order");
    if (!invoicePrefill && !laybyPrefill && !orderPrefill) {
      return;
    }
    prefillConsumed.current = true;
    if (invoicePrefill) {
      setSourceType("invoice");
      setInvoiceId(invoicePrefill);
    } else if (laybyPrefill) {
      setSourceType("layby");
      setLaybyId(laybyPrefill);
    } else if (orderPrefill) {
      setSourceType("sales_order");
      setSalesOrderId(orderPrefill);
    }
    setCreateOpen(true);
    const next = new URLSearchParams(searchParams.toString());
    next.delete("invoice");
    next.delete("layby");
    next.delete("order");
    const qs = next.toString();
    router.replace(qs ? `/deliveries?${qs}` : "/deliveries");
  }, [canMutate, searchParams, router]);

  const formValid = Boolean(
    locationId &&
      ((sourceType === "invoice" && invoiceId) ||
        (sourceType === "layby" && laybyId) ||
        (sourceType === "sales_order" && salesOrderId)),
  );

  function resetCreateForm() {

    setError(null);
    setSourceType("invoice");
    setInvoiceId("");
    setLaybyId("");
    setSalesOrderId("");
    setSourceQuery("");
    setNotes("");
    setLocationId(null);
  }

  async function handleCreate() {
    if (!formValid) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createDelivery({
        source_type: sourceType,
        invoice_id: sourceType === "invoice" ? invoiceId : undefined,
        layby_id: sourceType === "layby" ? laybyId : undefined,
        sales_order_id: sourceType === "sales_order" ? salesOrderId : undefined,
        location_id: locationId,
        notes: notes.trim() || undefined,
      });
      setCreateOpen(false);
      resetCreateForm();
      await loadDeliveries();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create delivery.");
    } finally {
      setSaving(false);
    }
  }

  async function handlePack(deliveryId: string) {
    setActionId(deliveryId);
    setError(null);
    try {
      await packDelivery(deliveryId);
      await loadDeliveries();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to pack delivery.");
    } finally {
      setActionId(null);
    }
  }

  async function handleLoad(deliveryId: string) {
    setActionId(deliveryId);
    setError(null);
    try {
      await loadDelivery(deliveryId);
      await loadDeliveries();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load delivery.");
    } finally {
      setActionId(null);
    }
  }

  async function handleComplete(deliveryId: string) {
    setActionId(deliveryId);
    setError(null);
    try {
      await completeDelivery(deliveryId);
      await loadDeliveries();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to mark delivery as delivered.");
    } finally {
      setActionId(null);
    }
  }

  async function handleCancel(deliveryId: string) {
    setActionId(deliveryId);
    setError(null);
    try {
      await cancelDelivery(deliveryId);
      await loadDeliveries();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Failed to cancel delivery.");
      }
    } finally {
      setActionId(null);
    }
  }

  const deliveryById = useMemo(
    () => Object.fromEntries(deliveries.map((entry) => [entry.id, entry])),
    [deliveries],
  );

  const rows: DeliveryRow[] = deliveries.map((entry) => ({
      id: entry.id,
      delivery_number: entry.delivery_number,
      source: sourceLabel(entry),
      customer_name: entry.customer_name,
      location_name: entry.location_name,
      status: entry.status,
      delivery_date: formatDate(entry.delivery_date),
      actions: entry.id,
    }));

  async function openDetail(entry: DeliveryListItem) {
    setError(null);
    try {
      const delivery = await getDelivery(entry.id);
      setSelectedDelivery(delivery);
      setDetailOpen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load delivery.");
    }
  }

  return (
    <Stack gap={6}>
      <div className="firstout-page-header">
        <div>
          <h1 className="cds--type-productive-heading-04">Deliveries</h1>
          <p className="cds--type-body-01">
            Pack and dispatch outbound deliveries from paid invoices, laybys, or sales orders.
          </p>
        </div>
        {canMutate ? (
          <Button
            onClick={() => {
              resetCreateForm();
              setCreateOpen(true);
            }}
          >
            New delivery
          </Button>
        ) : null}
      </div>

      <ErrorNotice error={error} onClose={() => setError(null)} />

      {loading ? (
        <DeliveriesLoading />
      ) : total === 0 ? (
        <InlineNotification
          kind="info"
          title="No deliveries"
          subtitle="No outbound deliveries have been recorded yet."
          hideCloseButton
          lowContrast
        />
      ) : (
        <>
        <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
          {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Deliveries" description="Outbound packing and dispatch">
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
                    const entry = deliveryById[row.id];
                    const busy = actionId === row.id;
                    return (
                      <TableRow
                        {...getRowProps({ row })}
                        key={row.id}
                        onClick={() => entry && openDetail(entry)}
                        style={{ cursor: entry ? "pointer" : undefined }}
                      >
                        {row.cells.map((cell) => {
                          if (cell.info.header === "status" && entry) {
                            return (
                              <TableCell key={cell.id}>
                                <Tag type={statusTagType(entry.status)}>
                                  {statusLabel(entry.status)}
                                </Tag>
                              </TableCell>
                            );
                          }
                          if (cell.info.header === "actions" && entry) {
                            return (
                              <TableCell key={cell.id}>
                                {entry.status === "draft" && canMutate ? (
                                  <Stack gap={3} orientation="horizontal">
                                    <Button
                                      kind="ghost"
                                      size="sm"
                                      disabled={busy}
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        void handlePack(entry.id);
                                      }}
                                    >
                                      {busy ? "Packing…" : "Pack"}
                                    </Button>
                                    <Button
                                      kind="ghost"
                                      size="sm"
                                      disabled={busy}
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        void handleCancel(entry.id);
                                      }}
                                    >
                                      Cancel
                                    </Button>
                                  </Stack>
                                ) : entry.status === "packed" && canMutate ? (
                                  <Stack gap={3} orientation="horizontal">
                                    <Button
                                      kind="ghost"
                                      size="sm"
                                      disabled={busy}
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        void handleLoad(entry.id);
                                      }}
                                    >
                                      {busy ? "Loading…" : "Load"}
                                    </Button>
                                    <Button
                                      kind="ghost"
                                      size="sm"
                                      disabled={busy}
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        void handleComplete(entry.id);
                                      }}
                                    >
                                      {busy ? "Saving…" : "Mark delivered"}
                                    </Button>
                                  </Stack>
                                ) : entry.status === "loaded" && canMutate ? (
                                  <Button
                                    kind="ghost"
                                    size="sm"
                                    disabled={busy}
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      void handleComplete(entry.id);
                                    }}
                                  >
                                    {busy ? "Saving…" : "Mark delivered"}
                                  </Button>
                                ) : (
                                  "—"
                                )}
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
        </>
      )}

      <Modal
        open={createOpen}
        modalHeading="New delivery"
        primaryButtonText={saving ? "Creating…" : "Create delivery"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || !formValid || sourceLoading}
        onRequestClose={() => setCreateOpen(false)}
        onRequestSubmit={() => void handleCreate()}
      >
        <Stack gap={5}>
          <Select
            id="delivery-source-type"
            labelText="Source type"
            value={sourceType}
            onChange={(event) => {
              const next = event.target.value as DeliverySourceType;
              setSourceType(next);
              setInvoiceId("");
              setLaybyId("");
              setSalesOrderId("");
              setSourceQuery("");
            }}
          >
            <SelectItem value="invoice" text="Invoice" />
            <SelectItem value="layby" text="Layby" />
            <SelectItem value="sales_order" text="Sales order" />
          </Select>
          {sourceType === "invoice" ? (
            <ServerSearchComboBox
              key="delivery-invoice"
              id="delivery-invoice"
              titleText="Invoice"
              placeholder="Search paid invoices…"
              items={invoiceOptions}
              selectedId={invoiceId}
              onSearch={setSourceQuery}
              onSelect={(option) => setInvoiceId(option?.id ?? "")}
            />
          ) : sourceType === "sales_order" ? (
            <ServerSearchComboBox
              key="delivery-sales-order"
              id="delivery-sales-order"
              titleText="Sales order"
              placeholder="Search sales orders…"
              items={salesOrderOptions}
              selectedId={salesOrderId}
              onSearch={setSourceQuery}
              onSelect={(option) => setSalesOrderId(option?.id ?? "")}
            />
          ) : (
            <ServerSearchComboBox
              key="delivery-layby"
              id="delivery-layby"
              titleText="Layby"
              placeholder="Search laybys…"
              items={laybyOptions}
              selectedId={laybyId}
              onSearch={setSourceQuery}
              onSelect={(option) => setLaybyId(option?.id ?? "")}
            />
          )}
          <Select
            id="delivery-location"
            labelText="Dispatch location"
            value={locationId}
            onChange={(event) => setLocationId(event.target.value)}
            helperText={locations.length === 0 ? "No active locations available" : undefined}
          >
            <SelectItem value="" text="Select a location" />
            {locations.map((entry) => (
              <SelectItem key={entry.id} value={entry.id} text={entry.name} />
            ))}
          </Select>
          {sourceLoading ? (
            <p className="cds--type-body-01">Loading line preview…</p>
          ) : sourcePreview ? (
            <Stack gap={3}>
              <p className="cds--type-label-01">Line preview</p>
              <ul className="cds--type-body-01" style={{ margin: 0, paddingLeft: "1.25rem" }}>
                {"lines" in sourcePreview
                  ? sourcePreview.lines.map((line) => (
                      <li key={line.id}>
                        {"our_ref" in line
                          ? `${line.our_ref} — ${line.name} × ${line.qty}`
                          : `${line.description} × ${line.qty}`}
                      </li>
                    ))
                  : null}
              </ul>
            </Stack>
          ) : null}
          <TextArea
            id="delivery-notes"
            labelText="Notes (optional)"
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            rows={3}
          />
        </Stack>
      </Modal>

      <Modal
        open={detailOpen}
        modalHeading="Delivery details"
        passiveModal
        onRequestClose={() => setDetailOpen(false)}
      >
        {selectedDelivery ? (
          <Stack gap={4}>
            <p className="cds--type-body-01">
              <strong>{selectedDelivery.delivery_number}</strong> — {selectedDelivery.customer_name}
            </p>
            <p className="cds--type-body-01">
              Source: {sourceLabel(selectedDelivery)} ({selectedDelivery.source_type})
            </p>
            <p className="cds--type-body-01">Location: {selectedDelivery.location_name}</p>
            <p className="cds--type-body-01">
              Status:{" "}
              <Tag type={statusTagType(selectedDelivery.status)}>
                {statusLabel(selectedDelivery.status)}
              </Tag>
            </p>
            <p className="cds--type-body-01">
              Delivery date: {formatDate(selectedDelivery.delivery_date)}
            </p>
            {selectedDelivery.notes ? (
              <p className="cds--type-body-01">Notes: {selectedDelivery.notes}</p>
            ) : null}
            <Stack gap={3}>
              <p className="cds--type-label-01">Lines</p>
              <ul className="cds--type-body-01" style={{ margin: 0, paddingLeft: "1.25rem" }}>
                {selectedDelivery.lines.map((line) => (
                  <li key={line.id}>
                    {line.description} × {line.qty}
                  </li>
                ))}
              </ul>
            </Stack>
          </Stack>
        ) : null}
      </Modal>
    </Stack>
  );
}

function DeliveriesLoading({ route = false }: { route?: boolean }) {
  const table = (
    <PageLoading
      label="Loading deliveries…"
      title="Deliveries"
      description="Outbound packing and dispatch"
      columns={TABLE_HEADERS.map(({ header }) => header)}
      pagination
    />
  );
  return route ? (
    <Stack gap={6}>
      <div>
        <h1 className="cds--type-productive-heading-04">Deliveries</h1>
        <p className="cds--type-body-01">Pack and dispatch outbound deliveries from paid invoices, laybys, or sales orders.</p>
      </div>
      {table}
    </Stack>
  ) : table;
}

export default function DeliveriesPage() {
  return (
    <Suspense fallback={<DeliveriesLoading route />}>
      <DeliveriesPageContent />
    </Suspense>
  );
}

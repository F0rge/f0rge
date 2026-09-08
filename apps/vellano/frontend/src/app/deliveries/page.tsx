"use client";

import {
  Button,
  DataTable,
  InlineNotification,
  Modal,
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
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  ApiError,
  cancelDelivery,
  canMutateDeliveries,
  completeDelivery,
  createDelivery,
  getInvoice,
  getLayby,
  isActiveLocation,
  isInvoiceFullyPaid,
  listDeliveries,
  listInvoices,
  listLaybys,
  listLocations,
  packDelivery,
  type Delivery,
  type DeliverySourceType,
  type DeliveryStatus,
  type Invoice,
  type Layby,
  type Location,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

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
  if (status === "delivered") {
    return "Delivered";
  }
  return "Cancelled";
}

function statusTagType(status: DeliveryStatus): "blue" | "teal" | "green" | "gray" {
  if (status === "draft") {
    return "blue";
  }
  if (status === "packed") {
    return "teal";
  }
  if (status === "delivered") {
    return "green";
  }
  return "gray";
}

function sourceLabel(entry: Delivery): string {
  if (entry.source_type === "invoice") {
    return entry.invoice_number ?? "Invoice";
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
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [laybys, setLaybys] = useState<Layby[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedDelivery, setSelectedDelivery] = useState<Delivery | null>(null);
  const [saving, setSaving] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null);
  const [sourceType, setSourceType] = useState<DeliverySourceType>("invoice");
  const [invoiceId, setInvoiceId] = useState("");
  const [laybyId, setLaybyId] = useState("");
  const [locationId, setLocationId] = useState("");
  const [notes, setNotes] = useState("");
  const [sourcePreview, setSourcePreview] = useState<Invoice | Layby | null>(null);
  const [sourceLoading, setSourceLoading] = useState(false);
  const prefillConsumed = useRef(false);

  const paidInvoices = useMemo(
    () => invoices.filter(isInvoiceFullyPaid),
    [invoices],
  );

  const eligibleLaybys = useMemo(
    () => laybys.filter((entry) => entry.status !== "cancelled"),
    [laybys],
  );

  const loadDeliveries = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listDeliveries();
      setDeliveries(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load deliveries.");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadCreateData = useCallback(async () => {
    try {
      const [invoiceData, laybyData, locationData] = await Promise.all([
        listInvoices(),
        listLaybys(),
        listLocations(),
      ]);
      const active = locationData.filter(isActiveLocation);
      setInvoices(invoiceData);
      setLaybys(laybyData);
      setLocations(active);
      setLocationId((current) => current || defaultLocationId(active));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load create form data.");
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadDeliveries();
    }
  }, [user, loadDeliveries]);

  useEffect(() => {
    if (createOpen && canMutate) {
      void loadCreateData();
    }
  }, [createOpen, canMutate, loadCreateData]);

  useEffect(() => {
    if (!canMutate || prefillConsumed.current) {
      return;
    }
    const invoicePrefill = searchParams.get("invoice");
    const laybyPrefill = searchParams.get("layby");
    if (!invoicePrefill && !laybyPrefill) {
      return;
    }
    prefillConsumed.current = true;
    if (invoicePrefill) {
      setSourceType("invoice");
      setInvoiceId(invoicePrefill);
    } else if (laybyPrefill) {
      setSourceType("layby");
      setLaybyId(laybyPrefill);
    }
    setCreateOpen(true);
    const next = new URLSearchParams(searchParams.toString());
    next.delete("invoice");
    next.delete("layby");
    const qs = next.toString();
    router.replace(qs ? `/deliveries?${qs}` : "/deliveries");
  }, [canMutate, searchParams, router]);

  useEffect(() => {
    if (sourceType === "invoice") {
      if (!invoiceId) {
        setSourcePreview(null);
        return;
      }
      let cancelled = false;
      setSourceLoading(true);
      getInvoice(invoiceId)
        .then((invoice) => {
          if (!cancelled) {
            setSourcePreview(invoice);
          }
        })
        .catch((err) => {
          if (!cancelled) {
            setError(err instanceof Error ? err.message : "Failed to load invoice.");
            setSourcePreview(null);
          }
        })
        .finally(() => {
          if (!cancelled) {
            setSourceLoading(false);
          }
        });
      return () => {
        cancelled = true;
      };
    }
    if (!laybyId) {
      setSourcePreview(null);
      return;
    }
    let cancelled = false;
    setSourceLoading(true);
    getLayby(laybyId)
      .then((layby) => {
        if (!cancelled) {
          setSourcePreview(layby);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load layby.");
          setSourcePreview(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setSourceLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [sourceType, invoiceId, laybyId]);

  const formValid = Boolean(
    locationId &&
      ((sourceType === "invoice" && invoiceId) || (sourceType === "layby" && laybyId)),
  );

  function resetCreateForm() {
    setSourceType("invoice");
    setInvoiceId("");
    setLaybyId("");
    setNotes("");
    setSourcePreview(null);
    setLocationId(defaultLocationId(locations));
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

  const rows: DeliveryRow[] = deliveries
    .slice()
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
    .map((entry) => ({
      id: entry.id,
      delivery_number: entry.delivery_number,
      source: sourceLabel(entry),
      customer_name: entry.customer_name,
      location_name: entry.location_name,
      status: entry.status,
      delivery_date: formatDate(entry.delivery_date),
      actions: entry.id,
    }));

  function openDetail(entry: Delivery) {
    setSelectedDelivery(entry);
    setDetailOpen(true);
  }

  return (
    <Stack gap={6}>
      <div className="vellano-page-header">
        <div>
          <h1 className="cds--type-productive-heading-04">Deliveries</h1>
          <p className="cds--type-body-01">
            Pack and dispatch outbound deliveries from fully paid invoices or active laybys.
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
        <p className="cds--type-body-01">Loading deliveries…</p>
      ) : deliveries.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No deliveries"
          subtitle="No outbound deliveries have been recorded yet."
          hideCloseButton
          lowContrast
        />
      ) : (
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
              setSourcePreview(null);
            }}
          >
            <SelectItem value="invoice" text="Invoice" />
            <SelectItem value="layby" text="Layby" />
          </Select>
          {sourceType === "invoice" ? (
            <Select
              id="delivery-invoice"
              labelText="Invoice"
              value={invoiceId}
              onChange={(event) => setInvoiceId(event.target.value)}
            >
              <SelectItem value="" text="Select a paid invoice" />
              {paidInvoices.map((invoice) => (
                <SelectItem
                  key={invoice.id}
                  value={invoice.id}
                  text={`${invoice.invoice_number} — ${invoice.customer_name}`}
                />
              ))}
            </Select>
          ) : (
            <Select
              id="delivery-layby"
              labelText="Layby"
              value={laybyId}
              onChange={(event) => setLaybyId(event.target.value)}
            >
              <SelectItem value="" text="Select a layby" />
              {eligibleLaybys.map((layby) => (
                <SelectItem
                  key={layby.id}
                  value={layby.id}
                  text={`${layby.layby_number} — ${layby.customer_name}`}
                />
              ))}
            </Select>
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

export default function DeliveriesPage() {
  return (
    <Suspense fallback={<p className="cds--type-body-01">Loading deliveries…</p>}>
      <DeliveriesPageContent />
    </Suspense>
  );
}

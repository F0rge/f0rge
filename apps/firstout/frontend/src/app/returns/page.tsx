"use client";

import {
  Button,
  ComboBox,
  DataTable,
  InlineNotification,
  Modal,
  NumberInput,
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
import { DocumentExport } from "@carbon/icons-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  ApiError,
  RETURN_DISPOSITION_LABELS,
  RETURN_REASON_LABELS,
  RETURN_REASONS,
  canMutateReturns,
  cancelReturn,
  completeReturn,
  createReturn,
  getInvoice,
  isActiveLocation,
  listInvoices,
  listLocations,
  listReturns,
  type Invoice,
  type InvoiceListItem,
  type Location,
  type StockReturnListItem,
  type StockReturnDisposition,
  type StockReturnReason,
  type StockReturnStatus,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { downloadCsv } from "@/lib/csv";

const TABLE_HEADERS = [
  { key: "return_number", header: "Return ID" },
  { key: "invoice_number", header: "Original Sale" },
  { key: "customer_name", header: "Customer" },
  { key: "status", header: "Status" },
  { key: "created_at", header: "Date" },
  { key: "actions", header: "Action" },
] as const;

type ReturnRow = {
  id: string;
  return_number: string;
  invoice_number: string;
  customer_name: string;
  status: string;
  created_at: string;
  actions: string;
};

type InvoiceOption = {
  id: string;
  label: string;
};

function invoiceToOption(invoice: InvoiceListItem): InvoiceOption {
  return {
    id: invoice.id,
    label: `${invoice.invoice_number} — ${invoice.customer_name}`,
  };
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-ZA");
}

function statusLabel(status: StockReturnStatus): string {
  if (status === "draft") {
    return "Pending inspection";
  }
  if (status === "completed") {
    return "Completed";
  }
  return "Cancelled";
}

function statusTagType(status: StockReturnStatus): "blue" | "green" | "gray" {
  if (status === "draft") {
    return "blue";
  }
  if (status === "completed") {
    return "green";
  }
  return "gray";
}

function defaultLocationId(locations: Location[]): string {
  const bedfordview = locations.find((entry) => entry.name.toLowerCase() === "bedfordview");
  return bedfordview?.id ?? locations[0]?.id ?? "";
}

function invoiceCanRestock(invoice: Invoice | null): boolean {
  return Boolean(invoice?.lines.some((line) => line.sku_id));
}

function ReturnsPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useAuth();
  const canMutate = canMutateReturns(user);
  const [returns, setReturns] = useState<StockReturnListItem[]>([]);
  const [invoiceOptions, setInvoiceOptions] = useState<InvoiceOption[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null);
  const [invoiceId, setInvoiceId] = useState("");
  const [invoiceQuery, setInvoiceQuery] = useState("");
  const [debouncedInvoiceQuery, setDebouncedInvoiceQuery] = useState("");
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null);
  const [locationId, setLocationId] = useState("");
  const [reason, setReason] = useState<StockReturnReason | "">("");
  const [disposition, setDisposition] = useState<StockReturnDisposition>("write_off");
  const [notes, setNotes] = useState("");
  const [lineQtys, setLineQtys] = useState<Record<string, number | "">>({});
  const [invoiceLoading, setInvoiceLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const invoicePrefillConsumed = useRef(false);

  const canRestock = invoiceCanRestock(selectedInvoice);

  const loadReturns = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listReturns({
        limit: pageSize,
        offset: (page - 1) * pageSize,
      });
      setReturns(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load returns.");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  const loadCreateData = useCallback(async () => {
    try {
      const locationData = await listLocations();
      const active = locationData.filter(isActiveLocation);
      setLocations(active);
      setLocationId((current) => current || defaultLocationId(active));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load locations.");
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadReturns();
    }
  }, [user, loadReturns]);

  useEffect(() => {
    if (createOpen && canMutate) {
      void loadCreateData();
    }
  }, [createOpen, canMutate, loadCreateData]);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedInvoiceQuery(invoiceQuery), 300);
    return () => clearTimeout(timer);
  }, [invoiceQuery]);

  useEffect(() => {
    if (!createOpen || !canMutate) {
      return;
    }
    let cancelled = false;
    void listInvoices({ limit: 25, q: debouncedInvoiceQuery || undefined }).then((data) => {
      if (!cancelled) {
        setInvoiceOptions(data.items.map(invoiceToOption));
      }
    });
    return () => {
      cancelled = true;
    };
  }, [createOpen, canMutate, debouncedInvoiceQuery]);

  const selectedInvoiceOption = useMemo(
    () => invoiceOptions.find((option) => option.id === invoiceId) ?? null,
    [invoiceOptions, invoiceId],
  );

  useEffect(() => {
    const prefilled = searchParams.get("invoice");
    if (!prefilled || !canMutate || invoicePrefillConsumed.current) {
      return;
    }
    invoicePrefillConsumed.current = true;
    setInvoiceId(prefilled);
    setCreateOpen(true);
    const next = new URLSearchParams(searchParams.toString());
    next.delete("invoice");
    const qs = next.toString();
    router.replace(qs ? `/returns?${qs}` : "/returns");
  }, [canMutate, searchParams, router]);

  useEffect(() => {
    if (!invoiceId) {
      setSelectedInvoice(null);
      setLineQtys({});
      return;
    }
    let cancelled = false;
    setInvoiceLoading(true);
    getInvoice(invoiceId)
      .then((invoice) => {
        if (cancelled) {
          return;
        }
        setSelectedInvoice(invoice);
        const qtys: Record<string, number | ""> = {};
        for (const line of invoice.lines) {
          qtys[line.id] = 0;
        }
        setLineQtys(qtys);
        if (!invoiceCanRestock(invoice)) {
          setDisposition("write_off");
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load invoice.");
          setSelectedInvoice(null);
          setLineQtys({});
        }
      })
      .finally(() => {
        if (!cancelled) {
          setInvoiceLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [invoiceId]);

  const selectedLines = useMemo(() => {
    if (!selectedInvoice) {
      return [];
    }
    return selectedInvoice.lines
      .map((line) => {
        const qty = lineQtys[line.id];
        if (typeof qty !== "number" || qty <= 0) {
          return null;
        }
        const payload: { invoice_line_id: string; sku_id?: string; qty: number } = {
          invoice_line_id: line.id,
          qty,
        };
        if (line.sku_id) {
          payload.sku_id = line.sku_id;
        }
        return payload;
      })
      .filter((line): line is NonNullable<typeof line> => line !== null);
  }, [selectedInvoice, lineQtys]);

  const formValid = Boolean(
    invoiceId && locationId && reason && disposition && selectedLines.length > 0,
  );

  function resetCreateForm() {
    setInvoiceId("");
    setInvoiceQuery("");
    setSelectedInvoice(null);
    setLineQtys({});
    setReason("");
    setDisposition("write_off");
    setNotes("");
    setLocationId(defaultLocationId(locations));
  }

  async function handleCreate() {
    if (!formValid || !reason) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createReturn({
        invoice_id: invoiceId,
        location_id: locationId,
        reason,
        disposition,
        notes: notes.trim() || undefined,
        lines: selectedLines,
      });
      setCreateOpen(false);
      resetCreateForm();
      await loadReturns();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create return.");
    } finally {
      setSaving(false);
    }
  }

  async function handleComplete(returnId: string) {
    setActionId(returnId);
    setError(null);
    try {
      await completeReturn(returnId);
      await loadReturns();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to process return.");
    } finally {
      setActionId(null);
    }
  }

  async function handleCancel(returnId: string) {
    setActionId(returnId);
    setError(null);
    try {
      await cancelReturn(returnId);
      await loadReturns();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Failed to cancel return.");
      }
    } finally {
      setActionId(null);
    }
  }

  const returnById = useMemo(
    () => Object.fromEntries(returns.map((entry) => [entry.id, entry])),
    [returns],
  );

  const rows: ReturnRow[] = returns.map((entry) => ({
    id: entry.id,
    return_number: entry.return_number,
    invoice_number: entry.invoice_number,
    customer_name: "—",
    status: entry.status,
    created_at: formatDate(entry.created_at),
    actions: entry.id,
  }));

  return (
    <Stack gap={6}>
      <div className="firstout-page-header">
        <div>
          <h1 className="cds--type-productive-heading-04">Returns &amp; RMA</h1>
          <p className="cds--type-body-01">
            Process customer returns from till sales or invoices.
          </p>
        </div>
        <div className="firstout-catalogue-actions">
          <Button
            kind="secondary"
            renderIcon={DocumentExport}
            disabled={total === 0}
            onClick={() => {
              downloadCsv(
                "firstout-returns.csv",
                ["Return ID", "Original Sale", "Customer", "Status", "Date", "Location"],
                returns.map((entry) => [
                  entry.return_number,
                  entry.invoice_number,
                  "",
                  statusLabel(entry.status),
                  formatDate(entry.created_at),
                  entry.location_name,
                ]),
              );
            }}
          >
            Export List
          </Button>
          {canMutate ? (
            <Button
              onClick={() => {
                resetCreateForm();
                setCreateOpen(true);
              }}
            >
              New Return
            </Button>
          ) : null}
        </div>
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
        <p className="cds--type-body-01">Loading returns…</p>
      ) : total === 0 ? (
        <InlineNotification
          kind="info"
          title="No returns"
          subtitle="No returns have been recorded yet."
          hideCloseButton
          lowContrast
        />
      ) : (
        <>
        <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
          {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Returns" description="Customer returns and RMA requests">
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
                    const entry = returnById[row.id];
                    const busy = actionId === row.id;
                    return (
                      <TableRow {...getRowProps({ row })} key={row.id}>
                        {row.cells.map((cell) => {
                          if (cell.info.header === "return_number" && entry) {
                            return (
                              <TableCell key={cell.id}>
                                <div className="cds--type-body-compact-01">{entry.return_number}</div>
                                <div className="firstout-muted-text">
                                  {RETURN_REASON_LABELS[entry.reason]}
                                </div>
                              </TableCell>
                            );
                          }
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
                            if (entry.status === "draft" && canMutate) {
                              return (
                                <TableCell key={cell.id}>
                                  <Stack gap={3} orientation="horizontal">
                                    <Button
                                      kind="ghost"
                                      size="sm"
                                      disabled={busy}
                                      onClick={() => void handleComplete(entry.id)}
                                    >
                                      {busy ? "Processing…" : "Process"}
                                    </Button>
                                    <Button
                                      kind="ghost"
                                      size="sm"
                                      disabled={busy}
                                      onClick={() => void handleCancel(entry.id)}
                                    >
                                      Cancel
                                    </Button>
                                  </Stack>
                                </TableCell>
                              );
                            }
                            if (entry.status === "completed" && entry.credit_note_id) {
                              return (
                                <TableCell key={cell.id}>
                                  <Button
                                    kind="ghost"
                                    size="sm"
                                    onClick={() => router.push("/credit-notes")}
                                  >
                                    View CN
                                  </Button>
                                </TableCell>
                              );
                            }
                            return <TableCell key={cell.id}>—</TableCell>;
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
        modalHeading="New Return"
        primaryButtonText={saving ? "Creating…" : "Create return"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || !formValid || invoiceLoading}
        onRequestClose={() => setCreateOpen(false)}
        onRequestSubmit={() => void handleCreate()}
      >
        <Stack gap={5}>
          <ComboBox
            id="return-invoice"
            titleText="Invoice"
            placeholder="Search invoice number or customer…"
            items={invoiceOptions}
            itemToString={(item) => item?.label ?? ""}
            selectedItem={selectedInvoiceOption}
            shouldFilterItem={() => true}
            onInputChange={(value) => setInvoiceQuery(value)}
            onChange={({ selectedItem }) => {
              setInvoiceId(selectedItem?.id ?? "");
              if (selectedItem) {
                setInvoiceQuery(selectedItem.label);
              }
            }}
          />
          <Select
            id="return-location"
            labelText="Location"
            value={locationId}
            onChange={(event) => setLocationId(event.target.value)}
            helperText={locations.length === 0 ? "No active locations available" : undefined}
          >
            <SelectItem value="" text="Select a location" />
            {locations.map((entry) => (
              <SelectItem key={entry.id} value={entry.id} text={entry.name} />
            ))}
          </Select>
          <Select
            id="return-reason"
            labelText="Reason"
            value={reason}
            onChange={(event) => setReason(event.target.value as StockReturnReason | "")}
          >
            <SelectItem value="" text="Select a reason" />
            {RETURN_REASONS.map((entry) => (
              <SelectItem key={entry} value={entry} text={RETURN_REASON_LABELS[entry]} />
            ))}
          </Select>
          <Select
            id="return-disposition"
            labelText="Disposition"
            value={disposition}
            onChange={(event) =>
              setDisposition(event.target.value as StockReturnDisposition)
            }
            helperText={
              !canRestock && selectedInvoice
                ? "Restock is only available for till sales (invoices with SKU lines)."
                : undefined
            }
          >
            <SelectItem
              value="restock"
              text={RETURN_DISPOSITION_LABELS.restock}
              disabled={!canRestock}
            />
            <SelectItem value="write_off" text={RETURN_DISPOSITION_LABELS.write_off} />
          </Select>
          {invoiceLoading ? (
            <p className="cds--type-body-01">Loading invoice lines…</p>
          ) : selectedInvoice ? (
            <Stack gap={4}>
              <p className="cds--type-label-01">Return quantities</p>
              {selectedInvoice.lines.map((line) => (
                <NumberInput
                  key={line.id}
                  id={`return-line-${line.id}`}
                  label={`${line.description} (max ${line.qty})`}
                  min={0}
                  max={line.qty}
                  step={1}
                  value={lineQtys[line.id] ?? 0}
                  onChange={(_event, { value }) => {
                    setLineQtys((current) => ({
                      ...current,
                      [line.id]: value === "" ? "" : Number(value),
                    }));
                  }}
                />
              ))}
            </Stack>
          ) : null}
          <TextArea
            id="return-notes"
            labelText="Notes (optional)"
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            rows={3}
          />
        </Stack>
      </Modal>
    </Stack>
  );
}

export default function ReturnsPage() {
  return (
    <Suspense fallback={<p className="cds--type-body-01">Loading returns…</p>}>
      <ReturnsPageContent />
    </Suspense>
  );
}

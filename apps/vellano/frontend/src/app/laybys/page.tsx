"use client";

import { Printer } from "@carbon/icons-react";
import {
  Button,
  Checkbox,
  DataTable,
  InlineNotification,
  Modal,
  NumberInput,
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
  TextInput,
} from "@carbon/react";
import { useCallback, useEffect, useMemo, useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import {
  ApiError,
  addLaybyPayment,
  cancelLayby,
  canMutateLaybys,
  completeLayby,
  computeInvoicePreview,
  createContact,
  createLayby,
  formatPriceAmount,
  formatZarAmount,
  getLayby,
  isActiveLocation,
  listContacts,
  listLaybys,
  listLocations,
  listSkus,
  roundHalfUp,
  type Contact,
  type Layby,
  type LaybyTender,
  type Location,
  type Sku,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "layby_number", header: "Reference" },
  { key: "customer_name", header: "Customer" },
  { key: "items", header: "Items" },
  { key: "total_inc_vat", header: "Total" },
  { key: "amount_paid", header: "Paid" },
  { key: "balance", header: "Balance" },
  { key: "due_date", header: "Due Date" },
  { key: "status", header: "Status" },
  { key: "actions", header: "Action" },
] as const;

const VAT_RATE_LABEL = "15%";
const SUGGESTED_DEPOSIT_RATE = 0.2;

type StatusFilter = "all" | "active" | "overdue" | "ready";

type LaybyRow = {
  id: string;
  layby_number: string;
  customer_name: string;
  items: string;
  total_inc_vat: string;
  amount_paid: string;
  balance: string;
  due_date: string;
  status: string;
  actions: string;
};

type LineForm = {
  sku_id: string;
  qty: number | "";
};

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function addMonthsIso(months: number): string {
  const date = new Date();
  date.setMonth(date.getMonth() + months);
  return date.toISOString().slice(0, 10);
}

function formatDate(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-ZA");
}

function isOverdue(layby: Layby): boolean {
  if (layby.status !== "open") {
    return false;
  }
  return layby.due_date < todayIso();
}

function statusLabel(layby: Layby): string {
  if (layby.status === "completed") {
    return "Completed";
  }
  if (layby.status === "cancelled") {
    return "Cancelled";
  }
  if (layby.status === "ready") {
    return "Ready for collection";
  }
  if (isOverdue(layby)) {
    return "Overdue";
  }
  return "Active";
}

function statusTagType(layby: Layby): "blue" | "green" | "gray" | "red" {
  if (layby.status === "completed") {
    return "green";
  }
  if (layby.status === "cancelled") {
    return "gray";
  }
  if (layby.status === "ready") {
    return "green";
  }
  if (isOverdue(layby)) {
    return "red";
  }
  return "blue";
}

function formatItems(layby: Layby): string {
  if (layby.lines.length === 0) {
    return "—";
  }
  const first = layby.lines[0];
  const base = `${first.name} × ${first.qty}`;
  if (layby.lines.length === 1) {
    return base;
  }
  return `${base} +${layby.lines.length - 1}`;
}

function defaultLocationId(locations: Location[]): string {
  const bedfordview = locations.find((entry) => entry.name.toLowerCase() === "bedfordview");
  return bedfordview?.id ?? locations[0]?.id ?? "";
}

function emptyLine(): LineForm {
  return { sku_id: "", qty: 1 };
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function matchesStatusFilter(layby: Layby, filter: StatusFilter): boolean {
  if (filter === "all") {
    return true;
  }
  if (filter === "overdue") {
    return isOverdue(layby);
  }
  if (filter === "ready") {
    return layby.status === "ready";
  }
  return layby.status === "open" && !isOverdue(layby);
}

function printLaybyReceipt(layby: Layby): void {
  const printWindow = window.open("", "_blank", "noopener,noreferrer");
  if (!printWindow) {
    return;
  }
  const itemsHtml =
    layby.lines.length === 0
      ? "<p>—</p>"
      : `<ul>${layby.lines
          .map((line) => `<li>${escapeHtml(line.name)} × ${line.qty}</li>`)
          .join("")}</ul>`;
  printWindow.document.write(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Layby ${escapeHtml(layby.layby_number)}</title>
  <style>
    body { font-family: "IBM Plex Sans", sans-serif; margin: 1.5rem; color: #161616; }
    h1 { font-size: 1.25rem; font-weight: 600; margin-bottom: 1rem; }
    .row { margin-bottom: 0.5rem; }
    .label { color: #525252; }
    @media print { body { margin: 0; } }
  </style>
</head>
<body>
  <h1>Layby ${escapeHtml(layby.layby_number)}</h1>
  <div class="row"><span class="label">Customer:</span> ${escapeHtml(layby.customer_name)}</div>
  <div class="row"><span class="label">Items:</span></div>
  ${itemsHtml}
  <div class="row"><span class="label">Paid:</span> ${escapeHtml(formatZarAmount(layby.amount_paid))}</div>
  <div class="row"><span class="label">Balance:</span> ${escapeHtml(formatZarAmount(layby.balance))}</div>
  <div class="row"><span class="label">Due date:</span> ${escapeHtml(formatDate(layby.due_date))}</div>
</body>
</html>`);
  printWindow.document.close();
  printWindow.focus();
  printWindow.print();
}

function sumLinesExVat(lines: LineForm[], skusById: Map<string, Sku>): number {
  return lines.reduce((sum, line) => {
    if (!line.sku_id || typeof line.qty !== "number" || line.qty <= 0) {
      return sum;
    }
    const sku = skusById.get(line.sku_id);
    if (!sku?.retail_ex_vat) {
      return sum;
    }
    return sum + line.qty * Number(sku.retail_ex_vat);
  }, 0);
}

export default function LaybysPage() {
  return (
    <Suspense fallback={<p className="cds--type-body-01">Loading laybys…</p>}>
      <LaybysPageContent />
    </Suspense>
  );
}

function LaybysPageContent() {
  const { user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const canMutate = canMutateLaybys(user);
  const [laybys, setLaybys] = useState<Layby[]>([]);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [skus, setSkus] = useState<Sku[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [manageOpen, setManageOpen] = useState(false);
  const [selectedLayby, setSelectedLayby] = useState<Layby | null>(null);
  const [saving, setSaving] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [customerId, setCustomerId] = useState("");
  const [newCustomerName, setNewCustomerName] = useState("");
  const [creatingCustomer, setCreatingCustomer] = useState(false);
  const [lines, setLines] = useState<LineForm[]>([emptyLine()]);
  const [durationMonths, setDurationMonths] = useState<"3" | "6">("3");
  const [holdStock, setHoldStock] = useState(true);
  const [locationId, setLocationId] = useState("");
  const [depositAmount, setDepositAmount] = useState<number | "">("");
  const [tender, setTender] = useState<LaybyTender>("cash");
  const [paymentAmount, setPaymentAmount] = useState<number | "">("");
  const [paymentTender, setPaymentTender] = useState<LaybyTender>("cash");
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  const customers = useMemo(
    () => contacts.filter((entry) => entry.kind === "customer"),
    [contacts],
  );

  const skusById = useMemo(() => new Map(skus.map((sku) => [sku.id, sku])), [skus]);

  const locationOptions = useMemo(() => {
    const active = locations.filter(isActiveLocation);
    if (holdStock) {
      return active.filter((entry) => entry.type === "showroom");
    }
    return active;
  }, [locations, holdStock]);

  const dueDate = durationMonths === "3" ? addMonthsIso(3) : addMonthsIso(6);

  const subtotalExVat = sumLinesExVat(lines, skusById);
  const preview = computeInvoicePreview(subtotalExVat);
  const suggestedDeposit = roundHalfUp(preview.totalIncVat * SUGGESTED_DEPOSIT_RATE, 2);
  const numericDeposit = typeof depositAmount === "number" ? depositAmount : 0;
  const remainingBalance = Math.max(roundHalfUp(preview.totalIncVat - numericDeposit, 2), 0);
  const durationCount = durationMonths === "3" ? 3 : 6;
  const monthlyInstallment = roundHalfUp(remainingBalance / durationCount, 2);

  const validLines = lines
    .map((line) => {
      if (!line.sku_id || typeof line.qty !== "number" || line.qty <= 0) {
        return null;
      }
      return { sku_id: line.sku_id, qty: line.qty };
    })
    .filter((line): line is { sku_id: string; qty: number } => line !== null);

  const createFormValid = Boolean(
    customerId && locationId && validLines.length > 0 && subtotalExVat > 0 && numericDeposit >= 0,
  );

  const loadLaybys = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listLaybys();
      setLaybys(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load laybys.");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadCreateData = useCallback(async () => {
    try {
      const [contactData, locationData, skuData] = await Promise.all([
        listContacts(),
        listLocations(),
        listSkus(),
      ]);
      setContacts(contactData);
      setLocations(locationData);
      setSkus(skuData.filter((sku) => sku.retail_ex_vat));
      const active = locationData.filter(isActiveLocation);
      const showrooms = active.filter((entry) => entry.type === "showroom");
      setLocationId((current) => current || defaultLocationId(showrooms.length > 0 ? showrooms : active));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load layby form data.");
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadLaybys();
    }
  }, [user, loadLaybys]);

  useEffect(() => {
    if (createOpen && canMutate) {
      void loadCreateData();
    }
  }, [createOpen, canMutate, loadCreateData]);

  useEffect(() => {
    if (!locationOptions.some((entry) => entry.id === locationId)) {
      setLocationId(defaultLocationId(locationOptions));
    }
  }, [locationOptions, locationId]);

  const resetCreateForm = useCallback(() => {
    setCustomerId("");
    setNewCustomerName("");
    setLines([emptyLine()]);
    setDurationMonths("3");
    setHoldStock(true);
    setDepositAmount("");
    setTender("cash");
    const active = locations.filter(isActiveLocation);
    const showrooms = active.filter((entry) => entry.type === "showroom");
    setLocationId(defaultLocationId(showrooms.length > 0 ? showrooms : active));
  }, [locations]);

  useEffect(() => {
    if (!canMutate || searchParams.get("new") !== "1" || locations.length === 0) {
      return;
    }
    resetCreateForm();
    setCreateOpen(true);
    router.replace("/laybys", { scroll: false });
  }, [canMutate, searchParams, router, locations.length, resetCreateForm]);

  function resetManageForm() {
    setPaymentAmount("");
    setPaymentTender("cash");
  }

  async function handleCreateCustomer() {
    const name = newCustomerName.trim();
    if (!name) {
      return;
    }
    setCreatingCustomer(true);
    setError(null);
    try {
      const contact = await createContact({ name });
      setContacts((current) => [...current, contact]);
      setCustomerId(contact.id);
      setNewCustomerName("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create customer.");
    } finally {
      setCreatingCustomer(false);
    }
  }

  async function handleCreate() {
    if (!createFormValid) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const created = await createLayby({
        customer_id: customerId,
        location_id: locationId,
        due_date: dueDate,
        hold_stock: holdStock,
        deposit_amount: formatPriceAmount(numericDeposit),
        tender,
        lines: validLines,
      });
      setCreateOpen(false);
      resetCreateForm();
      await loadLaybys();
      printLaybyReceipt(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create layby.");
    } finally {
      setSaving(false);
    }
  }

  async function openManage(laybyId: string) {
    setError(null);
    try {
      const layby = await getLayby(laybyId);
      setSelectedLayby(layby);
      resetManageForm();
      setManageOpen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load layby.");
    }
  }

  async function refreshSelectedLayby() {
    if (!selectedLayby) {
      return;
    }
    const layby = await getLayby(selectedLayby.id);
    setSelectedLayby(layby);
    await loadLaybys();
  }

  async function handleRecordPayment() {
    if (!selectedLayby || typeof paymentAmount !== "number" || paymentAmount <= 0) {
      return;
    }
    setActionBusy(true);
    setError(null);
    try {
      await addLaybyPayment(selectedLayby.id, {
        amount: formatPriceAmount(paymentAmount),
        tender: paymentTender,
      });
      resetManageForm();
      await refreshSelectedLayby();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to record payment.");
    } finally {
      setActionBusy(false);
    }
  }

  async function handleComplete() {
    if (!selectedLayby) {
      return;
    }
    setActionBusy(true);
    setError(null);
    try {
      await completeLayby(selectedLayby.id);
      setManageOpen(false);
      setSelectedLayby(null);
      await loadLaybys();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to complete layby.");
    } finally {
      setActionBusy(false);
    }
  }

  async function handleCancel() {
    if (!selectedLayby) {
      return;
    }
    setActionBusy(true);
    setError(null);
    try {
      await cancelLayby(selectedLayby.id);
      setManageOpen(false);
      setSelectedLayby(null);
      await loadLaybys();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Failed to cancel layby.");
      }
    } finally {
      setActionBusy(false);
    }
  }

  const laybyById = useMemo(
    () => Object.fromEntries(laybys.map((entry) => [entry.id, entry])),
    [laybys],
  );

  const filteredLaybys = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return laybys
      .slice()
      .sort((a, b) => b.created_at.localeCompare(a.created_at))
      .filter((entry) => {
        if (!matchesStatusFilter(entry, statusFilter)) {
          return false;
        }
        if (!query) {
          return true;
        }
        return (
          entry.layby_number.toLowerCase().includes(query) ||
          entry.customer_name.toLowerCase().includes(query) ||
          entry.location_name.toLowerCase().includes(query)
        );
      });
  }, [laybys, searchQuery, statusFilter]);

  const rows: LaybyRow[] = filteredLaybys.map((entry) => ({
    id: entry.id,
    layby_number: entry.layby_number,
    customer_name: entry.customer_name,
    items: formatItems(entry),
    total_inc_vat: formatZarAmount(entry.total_inc_vat),
    amount_paid: formatZarAmount(entry.amount_paid),
    balance: formatZarAmount(entry.balance),
    due_date: formatDate(entry.due_date),
    status: entry.status,
    actions: entry.id,
  }));

  const paymentFormValid =
    selectedLayby &&
    typeof paymentAmount === "number" &&
    paymentAmount > 0 &&
    selectedLayby.status !== "completed" &&
    selectedLayby.status !== "cancelled";

  return (
    <Stack gap={6}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="cds--type-productive-heading-04">Laybys</h1>
          <p className="cds--type-body-01">
            Manage open laybys, process deposits, and track layby inventory.
          </p>
        </div>
        {canMutate ? (
          <Button
            onClick={() => {
              resetCreateForm();
              setCreateOpen(true);
            }}
          >
            New layby
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
        <p className="cds--type-body-01">Loading laybys…</p>
      ) : (
        <div className="vellano-catalogue-panel">
          <div className="vellano-catalogue-toolbar">
            <div className="vellano-catalogue-toolbar__left">
              <TextInput
                id="laybys-search"
                labelText="Search laybys"
                hideLabel
                placeholder="Search by number or customer…"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                size="md"
              />
              <span className="vellano-catalogue-toolbar__divider" aria-hidden />
              <Select
                id="laybys-status-filter"
                labelText="Status"
                hideLabel
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
                style={{ width: "min(14rem, 100%)" }}
              >
                <SelectItem value="all" text="All" />
                <SelectItem value="active" text="Active" />
                <SelectItem value="overdue" text="Overdue" />
                <SelectItem value="ready" text="Ready for collection" />
              </Select>
            </div>
          </div>

          {laybys.length === 0 ? (
            <InlineNotification
              kind="info"
              title="No laybys"
              subtitle="No laybys have been recorded yet."
              hideCloseButton
              lowContrast
              style={{ margin: "1rem" }}
            />
          ) : (
            <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
              {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
                <TableContainer title="Laybys" description="Open laybys and payment progress">
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
                      {tableRows.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={headers.length}>
                            No laybys match the current filters.
                          </TableCell>
                        </TableRow>
                      ) : (
                        tableRows.map((row) => {
                          const entry = laybyById[row.id];
                          return (
                            <TableRow {...getRowProps({ row })} key={row.id}>
                              {row.cells.map((cell) => {
                                if (cell.info.header === "customer_name" && entry) {
                                  return (
                                    <TableCell key={cell.id}>
                                      <div className="cds--type-body-compact-01">
                                        {entry.customer_name}
                                      </div>
                                      <div className="vellano-muted-text">{entry.location_name}</div>
                                    </TableCell>
                                  );
                                }
                                if (cell.info.header === "status" && entry) {
                                  return (
                                    <TableCell key={cell.id}>
                                      <Tag type={statusTagType(entry)}>{statusLabel(entry)}</Tag>
                                    </TableCell>
                                  );
                                }
                                if (cell.info.header === "actions" && entry) {
                                  if (
                                    canMutate &&
                                    entry.status !== "completed" &&
                                    entry.status !== "cancelled"
                                  ) {
                                    return (
                                      <TableCell key={cell.id}>
                                        <Button
                                          kind="ghost"
                                          size="sm"
                                          onClick={() => void openManage(entry.id)}
                                        >
                                          Manage
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
                        })
                      )}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </DataTable>
          )}
        </div>
      )}

      <Modal
        open={createOpen}
        modalHeading="New layby"
        primaryButtonText={saving ? "Creating…" : "Confirm Layby & Print Receipt"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || !createFormValid}
        onRequestClose={() => setCreateOpen(false)}
        onRequestSubmit={() => void handleCreate()}
        size="lg"
      >
        <Stack gap={5}>
          <Select
            id="layby-customer"
            labelText="Customer"
            value={customerId}
            onChange={(event) => setCustomerId(event.target.value)}
          >
            <SelectItem value="" text="Select a customer" />
            {customers.map((customer) => (
              <SelectItem key={customer.id} value={customer.id} text={customer.name} />
            ))}
          </Select>
          <Stack gap={3} orientation="horizontal">
            <TextInput
              id="layby-new-customer"
              labelText="New customer"
              placeholder="Customer name"
              value={newCustomerName}
              onChange={(event) => setNewCustomerName(event.target.value)}
            />
            <Button
              kind="secondary"
              disabled={creatingCustomer || !newCustomerName.trim()}
              onClick={() => void handleCreateCustomer()}
              style={{ alignSelf: "flex-end" }}
            >
              {creatingCustomer ? "Adding…" : "Add"}
            </Button>
          </Stack>

          {lines.map((line, index) => (
            <Stack key={index} gap={4} orientation="horizontal">
              <Select
                id={`layby-sku-${index}`}
                labelText={index === 0 ? "SKU" : `SKU ${index + 1}`}
                value={line.sku_id}
                onChange={(event) => {
                  const next = [...lines];
                  next[index] = { ...next[index], sku_id: event.target.value };
                  setLines(next);
                }}
              >
                <SelectItem value="" text="Select SKU" />
                {skus.map((sku) => (
                  <SelectItem
                    key={sku.id}
                    value={sku.id}
                    text={`${sku.our_ref} — ${sku.name}`}
                  />
                ))}
              </Select>
              <NumberInput
                id={`layby-qty-${index}`}
                label="Quantity"
                min={1}
                value={line.qty}
                onChange={(_, { value }) => {
                  const next = [...lines];
                  next[index] = {
                    ...next[index],
                    qty: value === "" ? "" : typeof value === "number" ? value : Number(value),
                  };
                  setLines(next);
                }}
              />
              {lines.length > 1 ? (
                <Button
                  kind="ghost"
                  onClick={() => setLines(lines.filter((_, lineIndex) => lineIndex !== index))}
                  style={{ alignSelf: "flex-end" }}
                >
                  Remove
                </Button>
              ) : null}
            </Stack>
          ))}
          <Button kind="tertiary" onClick={() => setLines([...lines, emptyLine()])}>
            Add item
          </Button>

          <Select
            id="layby-duration"
            labelText="Duration"
            value={durationMonths}
            onChange={(event) => setDurationMonths(event.target.value as "3" | "6")}
            helperText={`Final payment due ${formatDate(dueDate)}`}
          >
            <SelectItem value="3" text="3 months" />
            <SelectItem value="6" text="6 months" />
          </Select>

          <Checkbox
            id="layby-hold-stock"
            labelText="Hold stock at showroom"
            checked={holdStock}
            onChange={(_, { checked }) => setHoldStock(checked)}
          />

          <Select
            id="layby-location"
            labelText="Location"
            value={locationId}
            onChange={(event) => setLocationId(event.target.value)}
            helperText={
              holdStock
                ? "Stock is reserved at the selected showroom."
                : "Stock remains in warehouse until final payment."
            }
          >
            <SelectItem value="" text="Select location" />
            {locationOptions.map((entry) => (
              <SelectItem key={entry.id} value={entry.id} text={entry.name} />
            ))}
          </Select>

          {subtotalExVat > 0 ? (
            <Stack gap={3}>
              <p className="cds--type-body-01">
                Total inc VAT ({VAT_RATE_LABEL}):{" "}
                <strong>{formatZarAmount(formatPriceAmount(preview.totalIncVat))}</strong>
              </p>
              <p className="cds--type-body-01">
                Suggested deposit (20%):{" "}
                {formatZarAmount(formatPriceAmount(suggestedDeposit))}
              </p>
              <NumberInput
                id="layby-deposit"
                label="Deposit Amount Paid Now (ZAR)"
                min={0}
                value={depositAmount}
                onChange={(_, { value }) => {
                  if (value === "") {
                    setDepositAmount("");
                  } else {
                    setDepositAmount(typeof value === "number" ? value : Number(value));
                  }
                }}
              />
              <p className="cds--type-body-01">
                Remaining balance:{" "}
                <strong>{formatZarAmount(formatPriceAmount(remainingBalance))}</strong>
              </p>
              <p className="cds--type-body-01">
                Monthly installment ({durationCount} months):{" "}
                <strong>{formatZarAmount(formatPriceAmount(monthlyInstallment))}</strong>
              </p>
              <Select
                id="layby-tender"
                labelText="Deposit tender"
                value={tender}
                onChange={(event) => setTender(event.target.value as LaybyTender)}
              >
                <SelectItem value="cash" text="Cash" />
                <SelectItem value="card" text="Card" />
              </Select>
            </Stack>
          ) : null}
        </Stack>
      </Modal>

      <Modal
        open={manageOpen}
        modalHeading={selectedLayby ? `Manage ${selectedLayby.layby_number}` : "Manage layby"}
        passiveModal
        onRequestClose={() => {
          setManageOpen(false);
          setSelectedLayby(null);
        }}
        size="lg"
      >
        {selectedLayby ? (
          <Stack gap={5}>
            <Stack gap={2}>
              <p className="cds--type-body-01">
                Customer: <strong>{selectedLayby.customer_name}</strong>
              </p>
              <p className="cds--type-body-01">
                Total: {formatZarAmount(selectedLayby.total_inc_vat)} · Paid:{" "}
                {formatZarAmount(selectedLayby.amount_paid)} · Balance:{" "}
                {formatZarAmount(selectedLayby.balance)}
              </p>
              <p className="cds--type-body-01">
                Due: {formatDate(selectedLayby.due_date)} ·{" "}
                <Tag type={statusTagType(selectedLayby)}>{statusLabel(selectedLayby)}</Tag>
              </p>
              <Button
                kind="ghost"
                size="sm"
                renderIcon={Printer}
                onClick={() => printLaybyReceipt(selectedLayby)}
              >
                Print receipt
              </Button>
            </Stack>

            <TableContainer title="Payment history">
              <Table size="sm">
                <TableHead>
                  <TableRow>
                    <TableHeader>Date</TableHeader>
                    <TableHeader>Amount</TableHeader>
                    <TableHeader>Tender</TableHeader>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {selectedLayby.payments.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={3}>No payments recorded yet.</TableCell>
                    </TableRow>
                  ) : (
                    selectedLayby.payments.map((payment) => (
                      <TableRow key={payment.id}>
                        <TableCell>{formatDate(payment.paid_on)}</TableCell>
                        <TableCell>{formatZarAmount(payment.amount)}</TableCell>
                        <TableCell>{payment.tender === "cash" ? "Cash" : "Card"}</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </TableContainer>

            {canMutate &&
            selectedLayby.status !== "completed" &&
            selectedLayby.status !== "cancelled" ? (
              <Stack gap={4}>
                <Stack gap={4} orientation="horizontal">
                  <NumberInput
                    id="layby-payment-amount"
                    label="Payment amount (ZAR)"
                    min={0}
                    value={paymentAmount}
                    onChange={(_, { value }) => {
                      if (value === "") {
                        setPaymentAmount("");
                      } else {
                        setPaymentAmount(typeof value === "number" ? value : Number(value));
                      }
                    }}
                  />
                  <Select
                    id="layby-payment-tender"
                    labelText="Tender"
                    value={paymentTender}
                    onChange={(event) => setPaymentTender(event.target.value as LaybyTender)}
                  >
                    <SelectItem value="cash" text="Cash" />
                    <SelectItem value="card" text="Card" />
                  </Select>
                </Stack>
                <Stack gap={3} orientation="horizontal">
                  <Button
                    kind="primary"
                    disabled={actionBusy || !paymentFormValid}
                    onClick={() => void handleRecordPayment()}
                  >
                    {actionBusy ? "Saving…" : "Record payment"}
                  </Button>
                  {selectedLayby.status === "ready" ? (
                    <Button
                      kind="secondary"
                      disabled={actionBusy}
                      onClick={() => void handleComplete()}
                    >
                      Complete
                    </Button>
                  ) : null}
                  {selectedLayby.status === "open" || selectedLayby.status === "ready" ? (
                    <Button
                      kind="danger--tertiary"
                      disabled={actionBusy}
                      onClick={() => void handleCancel()}
                    >
                      Cancel layby
                    </Button>
                  ) : null}
                </Stack>
              </Stack>
            ) : null}
          </Stack>
        ) : null}
      </Modal>
    </Stack>
  );
}

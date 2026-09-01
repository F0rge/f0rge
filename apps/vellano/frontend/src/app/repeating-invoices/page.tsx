"use client";

import {
  Button,
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
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  canMutateBooks,
  computeInvoicePreview,
  createRepeatingInvoice,
  formatPriceAmount,
  listContacts,
  listRepeatingInvoices,
  runRepeatingInvoice,
  sumInvoiceLinesExVat,
  type Contact,
  type CreateInvoiceLinePayload,
  type RepeatingInvoice,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "name", header: "Name" },
  { key: "customer_name", header: "Customer" },
  { key: "day_of_month", header: "Day of month" },
  { key: "next_date", header: "Next date" },
  { key: "status", header: "Status" },
  { key: "lines", header: "Lines" },
  { key: "actions", header: "" },
] as const;

type ScheduleRow = {
  id: string;
  name: string;
  customer_name: string;
  day_of_month: string;
  next_date: string;
  status: string;
  lines: string;
  actions: string;
};

type InvoiceLineForm = {
  description: string;
  qty: number | "";
  unit_ex_vat: string;
};

const emptyLine = (): InvoiceLineForm => ({
  description: "",
  qty: 1,
  unit_ex_vat: "",
});

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function defaultDayOfMonth(): number {
  return Math.min(new Date().getDate(), 28);
}

export default function RepeatingInvoicesPage() {
  const { user } = useAuth();
  const canMutate = canMutateBooks(user?.role);
  const [schedules, setSchedules] = useState<RepeatingInvoice[]>([]);
  const [customers, setCustomers] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [runningId, setRunningId] = useState<string | null>(null);
  const [customerId, setCustomerId] = useState("");
  const [name, setName] = useState("");
  const [dayOfMonth, setDayOfMonth] = useState<number | "">(defaultDayOfMonth());
  const [nextDate, setNextDate] = useState(todayIso());
  const [lines, setLines] = useState<InvoiceLineForm[]>([emptyLine()]);

  const customerNameById = useMemo(() => {
    const names = new Map<string, string>();
    for (const customer of customers) {
      names.set(customer.id, customer.name);
    }
    return names;
  }, [customers]);

  const loadSchedules = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [scheduleData, contactData] = await Promise.all([
        listRepeatingInvoices(),
        listContacts(),
      ]);
      setSchedules(scheduleData);
      setCustomers(contactData.filter((entry) => entry.kind === "customer"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load repeating invoices.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadSchedules();
    }
  }, [user, loadSchedules]);

  const preview = useMemo(() => {
    const subtotal = sumInvoiceLinesExVat(lines);
    return { subtotal, ...computeInvoicePreview(subtotal) };
  }, [lines]);

  const linesValid = lines.every(
    (line) =>
      line.description.trim() &&
      typeof line.qty === "number" &&
      line.qty > 0 &&
      line.unit_ex_vat.trim(),
  );
  const formValid =
    Boolean(customerId) &&
    Boolean(nextDate) &&
    typeof dayOfMonth === "number" &&
    dayOfMonth >= 1 &&
    dayOfMonth <= 28 &&
    lines.length >= 1 &&
    linesValid;

  function resetCreateForm() {
    setCustomerId("");
    setName("");
    setDayOfMonth(defaultDayOfMonth());
    setNextDate(todayIso());
    setLines([emptyLine()]);
  }

  function updateLine(index: number, patch: Partial<InvoiceLineForm>) {
    setLines((current) =>
      current.map((line, lineIndex) => (lineIndex === index ? { ...line, ...patch } : line)),
    );
  }

  function addLine() {
    setLines((current) => [...current, emptyLine()]);
  }

  function removeLine(index: number) {
    setLines((current) => (current.length > 1 ? current.filter((_, i) => i !== index) : current));
  }

  async function handleCreate() {
    if (!formValid || typeof dayOfMonth !== "number") {
      return;
    }
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const trimmedName = name.trim();
      await createRepeatingInvoice({
        customer_id: customerId,
        ...(trimmedName ? { name: trimmedName } : {}),
        day_of_month: dayOfMonth,
        next_date: nextDate,
        lines: lines.map(
          (line): CreateInvoiceLinePayload => ({
            description: line.description.trim(),
            qty: line.qty as number,
            unit_ex_vat: line.unit_ex_vat.trim(),
          }),
        ),
      });
      setCreateOpen(false);
      resetCreateForm();
      setSuccess("Schedule created.");
      await loadSchedules();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create repeating invoice.");
    } finally {
      setSaving(false);
    }
  }

  async function handleRun(id: string) {
    setRunningId(id);
    setError(null);
    setSuccess(null);
    try {
      const result = await runRepeatingInvoice(id);
      setSuccess(`Created ${result.invoice.invoice_number}.`);
      await loadSchedules();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run repeating invoice.");
    } finally {
      setRunningId(null);
    }
  }

  const rows: ScheduleRow[] = schedules.map((entry) => ({
    id: entry.id,
    name: entry.name?.trim() || "—",
    customer_name: customerNameById.get(entry.customer_id) ?? "—",
    day_of_month: String(entry.day_of_month),
    next_date: entry.next_date,
    status: entry.is_active ? "Active" : "Inactive",
    lines: String(entry.lines.length),
    actions: entry.id,
  }));

  const scheduleById = useMemo(
    () => Object.fromEntries(schedules.map((entry) => [entry.id, entry])),
    [schedules],
  );

  return (
    <Stack gap={6}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="cds--type-productive-heading-04">Repeating invoices</h1>
          <p className="cds--type-body-01">Monthly tax invoice schedules. Run now posts an INV-.</p>
        </div>
        {canMutate ? (
          <Button
            onClick={() => {
              resetCreateForm();
              setCreateOpen(true);
            }}
          >
            Create schedule
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

      {success ? (
        <InlineNotification
          kind="success"
          title="Done"
          subtitle={success}
          onCloseButtonClick={() => setSuccess(null)}
          lowContrast
        />
      ) : null}

      {loading ? (
        <p className="cds--type-body-01">Loading repeating invoices…</p>
      ) : schedules.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No repeating invoices"
          subtitle="No schedules have been created yet."
          hideCloseButton
          lowContrast
        />
      ) : (
        <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
          {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Repeating invoices" description="Monthly invoice schedules">
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
                    const entry = scheduleById[row.id];
                    const busy = runningId === row.id;
                    return (
                      <TableRow {...getRowProps({ row })} key={row.id}>
                        {row.cells.map((cell) => {
                          if (cell.info.header === "status" && entry) {
                            return (
                              <TableCell key={cell.id}>
                                <Tag type={entry.is_active ? "green" : "gray"}>
                                  {entry.is_active ? "Active" : "Inactive"}
                                </Tag>
                              </TableCell>
                            );
                          }
                          if (cell.info.header === "actions") {
                            return (
                              <TableCell key={cell.id}>
                                {canMutate && entry?.is_active ? (
                                  <Button
                                    kind="ghost"
                                    size="sm"
                                    disabled={busy}
                                    onClick={() => void handleRun(row.id)}
                                  >
                                    {busy ? "Running…" : "Run now"}
                                  </Button>
                                ) : null}
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
        modalHeading="Create repeating invoice"
        primaryButtonText={saving ? "Creating…" : "Create"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || !formValid}
        onRequestClose={() => setCreateOpen(false)}
        onRequestSubmit={() => void handleCreate()}
        size="lg"
      >
        <Stack gap={5}>
          <Select
            id="repeating-customer"
            labelText="Customer"
            value={customerId}
            onChange={(event) => setCustomerId(event.target.value)}
          >
            <SelectItem value="" text="Select a customer" />
            {customers.map((customer) => (
              <SelectItem key={customer.id} value={customer.id} text={customer.name} />
            ))}
          </Select>
          <TextInput
            id="repeating-name"
            labelText="Name (optional)"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <NumberInput
            id="repeating-day"
            label="Day of month"
            min={1}
            max={28}
            value={dayOfMonth}
            onChange={(_, { value }) =>
              setDayOfMonth(value === "" ? "" : Number(value))
            }
          />
          <TextInput
            id="repeating-next-date"
            labelText="Next date"
            type="date"
            value={nextDate}
            onChange={(event) => setNextDate(event.target.value)}
            required
          />
          <div>
            <p className="cds--label">Lines</p>
            <Stack gap={4}>
              {lines.map((line, index) => (
                <div
                  key={`line-${index}`}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "2fr 1fr 1fr auto",
                    gap: "0.5rem",
                    alignItems: "end",
                  }}
                >
                  <TextInput
                    id={`repeating-line-desc-${index}`}
                    labelText={index === 0 ? "Description" : ""}
                    hideLabel={index > 0}
                    value={line.description}
                    onChange={(event) => updateLine(index, { description: event.target.value })}
                  />
                  <NumberInput
                    id={`repeating-line-qty-${index}`}
                    label={index === 0 ? "Qty" : ""}
                    hideLabel={index > 0}
                    min={1}
                    value={line.qty}
                    onChange={(_, { value }) =>
                      updateLine(index, { qty: value === "" ? "" : Number(value) })
                    }
                  />
                  <TextInput
                    id={`repeating-line-unit-${index}`}
                    labelText={index === 0 ? "Unit ex VAT" : ""}
                    hideLabel={index > 0}
                    value={line.unit_ex_vat}
                    onChange={(event) => updateLine(index, { unit_ex_vat: event.target.value })}
                  />
                  {lines.length > 1 ? (
                    <Button kind="ghost" size="sm" onClick={() => removeLine(index)}>
                      Remove
                    </Button>
                  ) : (
                    <span />
                  )}
                </div>
              ))}
            </Stack>
            <Button kind="ghost" size="sm" onClick={addLine} style={{ marginTop: "0.5rem" }}>
              Add line
            </Button>
          </div>
          <div className="vellano-invoice-preview">
            <p className="cds--type-productive-heading-02">Preview (15% VAT)</p>
            <p className="cds--type-body-01">Ex VAT: R {formatPriceAmount(preview.subtotal)}</p>
            <p className="cds--type-body-01">VAT: R {formatPriceAmount(preview.vat)}</p>
            <p className="cds--type-body-01">
              <strong>Total inc VAT: R {formatPriceAmount(preview.totalIncVat)}</strong>
            </p>
          </div>
        </Stack>
      </Modal>
    </Stack>
  );
}

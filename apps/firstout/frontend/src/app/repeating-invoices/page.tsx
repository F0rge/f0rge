"use client";

import { ErrorNotice } from "@/components/error-notice";
import {
  Button,
  InlineNotification,
  Modal,
  NumberInput,
  Stack,
  TextInput,
} from "@carbon/react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { CustomerPicker } from "@/components/customer-picker";
import {
  canMutateBooks,
  createRepeatingInvoice,
  formatPriceAmount,
  formatZarAmount,
  listCustomers,
  apiFetch,
  previewInvoicePrices,
  runRepeatingInvoice,
  type CreateInvoiceLinePayload,
  type RepeatingInvoice,
} from "@/lib/api";
import { usePageError } from "@/hooks/use-page-error";
import { useAuth } from "@/lib/auth";
import { queryKeys, referenceQueries } from "@/lib/queries";
import { localIsoDate } from "@/lib/dates";
import { workspaceIdentity } from "@/lib/record-workspace";
import { RecordWorkspace, RecordDetails, RecordDetail, type RecordWorkspaceAdapter } from "@/components/record-workspace";

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

function defaultDayOfMonth(): number {
  return Math.min(new Date().getDate(), 28);
}

export default function RepeatingInvoicesPage() {
  const { user } = useAuth();
  return <RepeatingInvoicesContent key={workspaceIdentity(user)} />;
}

function RepeatingInvoicesContent() {
  const { user } = useAuth();
  const canMutate = canMutateBooks(user);
  const [refreshKey, setRefreshKey] = useState(0);
  const [editing, setEditing] = useState<RepeatingInvoice | null>(null);
  const [editName, setEditName] = useState("");
  const [editDay, setEditDay] = useState<number | "">(1);
  const [editDate, setEditDate] = useState("");
  const [runTarget, setRunTarget] = useState<RepeatingInvoice | null>(null);
  const customersQuery = useQuery({ ...referenceQueries.customers, enabled: Boolean(user) });
  const archivedQuery = useQuery({
    queryKey: [...queryKeys.customers, { archived: true }],
    queryFn: () => listCustomers({ archived: true }),
    enabled: Boolean(user),
  });
  const customers = useMemo(() => customersQuery.data ?? [], [customersQuery.data]);
  const archivedCustomers = useMemo(() => archivedQuery.data ?? [], [archivedQuery.data]);
  const loadFailure = customersQuery.error ?? archivedQuery.error;
  const { error, setError } = usePageError(loadFailure, "Failed to load repeating invoices.");
  const [success, setSuccess] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [runningId, setRunningId] = useState<string | null>(null);
  const [customerId, setCustomerId] = useState("");
  const [name, setName] = useState("");
  const [dayOfMonth, setDayOfMonth] = useState<number | "">(defaultDayOfMonth());
  const [nextDate, setNextDate] = useState(localIsoDate());
  const [lines, setLines] = useState<InvoiceLineForm[]>([emptyLine()]);

  const customerNameById = useMemo(() => {
    const names = new Map<string, string>();
    for (const customer of [...customers, ...archivedCustomers]) {
      names.set(customer.id, customer.name);
    }
    return names;
  }, [customers, archivedCustomers]);
  const archivedCustomerIds = useMemo(() => new Set(archivedCustomers.map((customer) => customer.id)), [archivedCustomers]);

  const linesValid = lines.every(
    (line) =>
      line.description.trim() &&
      typeof line.qty === "number" &&
      line.qty > 0 &&
      Number(line.unit_ex_vat) > 0,
  );
  const payloadLines = lines.map(
    (line): CreateInvoiceLinePayload => ({
      description: line.description.trim(),
      qty: line.qty as number,
      unit_ex_vat: line.unit_ex_vat.trim(),
    }),
  );
  // Totals as the books invoice service would price these lines today (Firstout ADR 0001).
  // Keyed on what changes the amounts, so typing a description does not refetch.
  const canPreview = Boolean(customerId) && linesValid;
  const amountLines = payloadLines.map(({ qty, unit_ex_vat }) => ({ description: "Line", qty, unit_ex_vat }));
  const previewQuery = useQuery({
    queryKey: ["repeating-invoice-preview", customerId, amountLines],
    queryFn: ({ signal }) => previewInvoicePrices({ customer_id: customerId, lines: amountLines }, signal),
    enabled: canPreview,
    placeholderData: keepPreviousData,
  });
  const preview = canPreview ? previewQuery.data : undefined;
  const previewStale = previewQuery.isPlaceholderData;
  const formValid =
    Boolean(customerId) &&
    Boolean(nextDate) &&
    typeof dayOfMonth === "number" &&
    dayOfMonth >= 1 &&
    dayOfMonth <= 28 &&
    lines.length >= 1 &&
    linesValid;

  function resetCreateForm() {

    setError(null);
    setCustomerId("");
    setName("");
    setDayOfMonth(defaultDayOfMonth());
    setNextDate(localIsoDate());
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
        lines: payloadLines,
      });
      setCreateOpen(false);
      resetCreateForm();
      setSuccess("Schedule created.");
      setRefreshKey((value) => value + 1);
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
      setRunTarget(null);
      setRefreshKey((value) => value + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to run repeating invoice.");
    } finally {
      setRunningId(null);
    }
  }

  function openEdit(item: RepeatingInvoice) {
    setError(null);
    setEditing(item); setEditName(item.name ?? ""); setEditDay(item.day_of_month); setEditDate(item.next_date);
  }

  async function saveEdit() {
    if (!editing || typeof editDay !== "number" || !editDate) return;
    setSaving(true); setError(null);
    try {
      await apiFetch<RepeatingInvoice>(`/repeating-invoices/${editing.id}`, {
        method: "PATCH", body: JSON.stringify({ name: editName.trim() || null, day_of_month: editDay, next_date: editDate }),
      });
      setEditing(null); setRefreshKey((value) => value + 1); setSuccess("Schedule updated.");
    } catch (err) { setError(err instanceof Error ? err.message : "Could not update schedule."); }
    finally { setSaving(false); }
  }

  return (
    <Stack gap={6}>
      <ErrorNotice error={error} onClose={() => setError(null)} />

      {success ? (
        <InlineNotification
          kind="success"
          title="Done"
          subtitle={success}
          onCloseButtonClick={() => setSuccess(null)}
          lowContrast
        />
      ) : null}

      <RecordWorkspace<RepeatingInvoice>
        adapter={{
          resource: "repeating-invoices", title: "Repeating invoices", singular: "schedule", breadcrumb: "Books",
          description: "Review monthly schedules, pause them and create invoices when ready.", defaultSort: "next_date",
          lifecycle: { activeLabel: "Active", archivedLabel: "Paused" },
          columns: [
            { key: "name", label: "Schedule / customer", render: (item) => item.name || "Unnamed schedule" },
            { key: "day_of_month", label: "Day of month", render: (item) => item.day_of_month, numeric: true },
            { key: "next_date", label: "Next invoice", render: (item) => item.next_date },
          ],
          filters: [
            { key: "name", label: "Schedule name", type: "text" },
            { key: "customer_name", label: "Customer", type: "text" },
            { key: "day_of_month", label: "Day of month", type: "number" },
            { key: "next_date", label: "Next invoice", type: "date" },
          ],
          bulkFields: [{ key: "day_of_month", label: "Day of month", type: "number" }, { key: "next_date", label: "Next invoice", type: "date" }],
          actions: canMutate ? [{ key: "edit", label: "Edit" }, { key: "pause", label: "Pause" }, { key: "resume", label: "Resume" }] : [],
          getTitle: (item) => item.name || "Unnamed schedule", getSubtitle: (item) => customerNameById.get(item.customer_id) ?? "Customer",
          canEdit: () => canMutate,
        } satisfies RecordWorkspaceAdapter<RepeatingInvoice>}
        refreshKey={refreshKey}
        onCreate={canMutate ? () => { resetCreateForm(); setCreateOpen(true); } : undefined}
        createLabel="Create schedule"
        onEdit={canMutate ? openEdit : undefined}
        renderDetails={(item) => <Stack gap={5}>
          <RecordDetails>
            <RecordDetail label="Customer">{customerNameById.get(item.customer_id) ?? item.customer_id}</RecordDetail>
            <RecordDetail label="Status">{item.is_active ? "Active" : "Paused"}</RecordDetail>
            <RecordDetail label="Day of month">{item.day_of_month}</RecordDetail>
            <RecordDetail label="Next invoice">{item.next_date}</RecordDetail>
          </RecordDetails>
          <div><h3 className="cds--type-heading-compact-01">Invoice lines</h3><ul>{item.lines.map((line) => <li key={line.id}>{line.description} × {line.qty} · R {formatPriceAmount(Number(line.unit_ex_vat))} ex VAT</li>)}</ul></div>
          {archivedCustomerIds.has(item.customer_id) ? <Button kind="ghost" href={`/customers/${item.customer_id}`}>Open archived customer</Button> :
            canMutate && item.is_active ? <Button kind="tertiary" disabled={runningId !== null} onClick={() => { setError(null); setRunTarget(item); }}>Run now</Button> : null}
        </Stack>}
      />
      <Modal open={editing !== null} modalHeading="Edit schedule"
        primaryButtonText={saving ? "Saving…" : "Save changes"} secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || typeof editDay !== "number" || editDay < 1 || editDay > 28 || !editDate}
        onRequestClose={() => { if (!saving) setEditing(null); }} onRequestSubmit={() => void saveEdit()}>
        <fieldset disabled={saving} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}><Stack gap={5}>
          <TextInput id="schedule-edit-name" labelText="Name" value={editName} onChange={(event) => setEditName(event.target.value)} />
          <NumberInput id="schedule-edit-day" label="Day of month" min={1} max={28} value={editDay} onChange={(_, { value }) => setEditDay(value === "" ? "" : Number(value))} />
          <TextInput id="schedule-edit-date" labelText="Next invoice" type="date" value={editDate} onChange={(event) => setEditDate(event.target.value)} />
        </Stack></fieldset>
      </Modal>
      <Modal open={runTarget !== null} modalHeading="Run invoice schedule"
        primaryButtonText={runningId ? "Creating invoice…" : "Create invoice"} secondaryButtonText="Cancel"
        primaryButtonDisabled={runningId !== null}
        onRequestClose={() => { if (!runningId) setRunTarget(null); }}
        onRequestSubmit={() => { if (runTarget) void handleRun(runTarget.id); }}>
        <p>Create a tax invoice from {runTarget?.name || "this schedule"}? This posts the invoice and advances the next date.</p>
      </Modal>

      <Modal
        open={createOpen}
        modalHeading="Create repeating invoice"
        primaryButtonText={saving ? "Creating…" : "Create"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || !formValid}
        onRequestClose={() => { if (!saving) setCreateOpen(false); }}
        onRequestSubmit={() => void handleCreate()}
        size="lg"
      >
        <fieldset disabled={saving} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}><Stack gap={5}>
          <CustomerPicker
            id="repeating-customer"
            customers={customers}
            selectedId={customerId}
            disabled={saving}
            onChange={setCustomerId}
          />
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
          <div className="firstout-invoice-preview">
            <p className="cds--type-productive-heading-02">Preview</p>
            {preview ? (
              <div style={previewStale ? { opacity: 0.5 } : undefined} aria-busy={previewStale}>
                {previewStale ? <p role="status" className="cds--type-helper-text-01">Updating…</p> : null}
                <p className="cds--type-body-01">Ex VAT: {formatZarAmount(preview.subtotal_ex_vat)}</p>
                <p className="cds--type-body-01">VAT: {formatZarAmount(preview.vat_amount)}</p>
                <p className="cds--type-body-01">
                  <strong>Total inc VAT: {formatZarAmount(preview.total_inc_vat)}</strong>
                </p>
              </div>
            ) : (
              <p role="status" className="cds--type-helper-text-01">
                {!canPreview
                  ? "Choose a customer and complete the lines to see the totals."
                  : previewQuery.isError
                    ? previewQuery.error.message
                    : "Working out the totals…"}
              </p>
            )}
          </div>
        </Stack></fieldset>
      </Modal>
    </Stack>
  );
}

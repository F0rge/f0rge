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
  TextInput,
} from "@carbon/react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  canMutateBooks,
  computeInvoicePreview,
  createInvoice,
  formatPriceAmount,
  formatZarAmount,
  listContacts,
  listInvoices,
  sumInvoiceLinesExVat,
  type Contact,
  type CreateInvoiceLinePayload,
  type Invoice,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "invoice_number", header: "Number" },
  { key: "customer_name", header: "Customer" },
  { key: "issue_date", header: "Issue date" },
  { key: "subtotal_ex_vat", header: "Ex VAT" },
  { key: "vat_amount", header: "VAT" },
  { key: "total_inc_vat", header: "Inc VAT" },
  { key: "balance", header: "Balance" },
  { key: "actions", header: "" },
] as const;

type InvoiceRow = {
  id: string;
  invoice_number: string;
  customer_name: string;
  issue_date: string;
  subtotal_ex_vat: string;
  vat_amount: string;
  total_inc_vat: string;
  balance: string;
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

export default function InvoicesPage() {
  const router = useRouter();
  const { user } = useAuth();
  const canMutate = canMutateBooks(user?.role);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [customers, setCustomers] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [customerId, setCustomerId] = useState("");
  const [issueDate, setIssueDate] = useState(todayIso());
  const [lines, setLines] = useState<InvoiceLineForm[]>([emptyLine()]);

  const loadInvoices = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listInvoices();
      setInvoices(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load invoices.");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadCreateData = useCallback(async () => {
    try {
      const contactData = await listContacts();
      setCustomers(contactData.filter((entry) => entry.kind === "customer"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load customers.");
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadInvoices();
    }
  }, [user, loadInvoices]);

  useEffect(() => {
    if (createOpen && canMutate) {
      void loadCreateData();
    }
  }, [createOpen, canMutate, loadCreateData]);

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
  const formValid = customerId && issueDate && lines.length >= 1 && linesValid;

  function resetCreateForm() {
    setCustomerId("");
    setIssueDate(todayIso());
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
    if (!formValid) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const payload = {
        customer_id: customerId,
        issue_date: issueDate,
        lines: lines.map(
          (line): CreateInvoiceLinePayload => ({
            description: line.description.trim(),
            qty: line.qty as number,
            unit_ex_vat: line.unit_ex_vat.trim(),
          }),
        ),
      };
      const created = await createInvoice(payload);
      setCreateOpen(false);
      resetCreateForm();
      router.push(`/invoices/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create invoice.");
    } finally {
      setSaving(false);
    }
  }

  const rows: InvoiceRow[] = invoices.map((entry) => ({
    id: entry.id,
    invoice_number: entry.invoice_number,
    customer_name: entry.customer_name,
    issue_date: entry.issue_date,
    subtotal_ex_vat: formatZarAmount(entry.subtotal_ex_vat),
    vat_amount: formatZarAmount(entry.vat_amount),
    total_inc_vat: formatZarAmount(entry.total_inc_vat),
    balance: formatZarAmount(entry.balance),
    actions: entry.id,
  }));

  return (
    <Stack gap={6}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="cds--type-productive-heading-04">Invoices</h1>
          <p className="cds--type-body-01">Tax invoices with 15% VAT.</p>
        </div>
        {canMutate ? (
          <Button
            onClick={() => {
              resetCreateForm();
              setCreateOpen(true);
            }}
          >
            Create invoice
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
        <p className="cds--type-body-01">Loading invoices…</p>
      ) : invoices.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No invoices"
          subtitle="No tax invoices have been created yet."
          hideCloseButton
          lowContrast
        />
      ) : (
        <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
          {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Invoices" description="All Vellano tax invoices">
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
                    <TableRow
                      {...getRowProps({ row })}
                      key={row.id}
                      onClick={() => router.push(`/invoices/${row.id}`)}
                      style={{ cursor: "pointer" }}
                    >
                      {row.cells.map((cell) => {
                        if (cell.info.header === "actions") {
                          return (
                            <TableCell key={cell.id}>
                              <Button
                                kind="ghost"
                                size="sm"
                                onClick={(event) => {
                                  event.stopPropagation();
                                  router.push(`/invoices/${row.id}`);
                                }}
                              >
                                Open
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

      <Modal
        open={createOpen}
        modalHeading="Create invoice"
        primaryButtonText={saving ? "Creating…" : "Create"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || !formValid}
        onRequestClose={() => setCreateOpen(false)}
        onRequestSubmit={() => void handleCreate()}
        size="lg"
      >
        <Stack gap={5}>
          <Select
            id="invoice-customer"
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
            id="invoice-issue-date"
            labelText="Issue date"
            type="date"
            value={issueDate}
            onChange={(event) => setIssueDate(event.target.value)}
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
                    id={`invoice-line-desc-${index}`}
                    labelText={index === 0 ? "Description" : ""}
                    hideLabel={index > 0}
                    value={line.description}
                    onChange={(event) => updateLine(index, { description: event.target.value })}
                  />
                  <NumberInput
                    id={`invoice-line-qty-${index}`}
                    label={index === 0 ? "Qty" : ""}
                    hideLabel={index > 0}
                    min={1}
                    value={line.qty}
                    onChange={(_, { value }) =>
                      updateLine(index, { qty: value === "" ? "" : Number(value) })
                    }
                  />
                  <TextInput
                    id={`invoice-line-unit-${index}`}
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

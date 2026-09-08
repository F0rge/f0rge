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
  TextArea,
} from "@carbon/react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  canMutateBooks,
  createCreditNote,
  downloadCreditNotePdf,
  formatZarAmount,
  listCreditNotes,
  listInvoices,
  type CreditNote,
  type Invoice,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "credit_note_number", header: "Number" },
  { key: "invoice_number", header: "Invoice" },
  { key: "issue_date", header: "Issue date" },
  { key: "reason", header: "Reason" },
  { key: "subtotal_ex_vat", header: "Ex VAT" },
  { key: "vat_amount", header: "VAT" },
  { key: "total_inc_vat", header: "Inc VAT" },
  { key: "actions", header: "" },
] as const;

type CreditNoteRow = {
  id: string;
  invoice_id: string;
  credit_note_number: string;
  invoice_number: string;
  issue_date: string;
  reason: string;
  subtotal_ex_vat: string;
  vat_amount: string;
  total_inc_vat: string;
  actions: string;
};

export default function CreditNotesPage() {
  const router = useRouter();
  const { user } = useAuth();
  const canMutate = canMutateBooks(user);
  const [creditNotes, setCreditNotes] = useState<CreditNote[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [invoiceId, setInvoiceId] = useState("");
  const [reason, setReason] = useState("");

  const creditedInvoiceIds = useMemo(
    () => new Set(creditNotes.map((entry) => entry.invoice_id)),
    [creditNotes],
  );

  const loadCreditNotes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listCreditNotes();
      setCreditNotes(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load credit notes.");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadCreateData = useCallback(async () => {
    try {
      const [invoiceData, creditNoteData] = await Promise.all([
        listInvoices(),
        listCreditNotes(),
      ]);
      setInvoices(invoiceData);
      setCreditNotes(creditNoteData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load invoices.");
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadCreditNotes();
    }
  }, [user, loadCreditNotes]);

  useEffect(() => {
    if (createOpen && canMutate) {
      void loadCreateData();
    }
  }, [createOpen, canMutate, loadCreateData]);

  const availableInvoices = useMemo(
    () => invoices.filter((invoice) => !creditedInvoiceIds.has(invoice.id)),
    [invoices, creditedInvoiceIds],
  );

  const formValid = Boolean(invoiceId);

  function resetCreateForm() {
    setInvoiceId("");
    setReason("");
  }

  async function handleCreate() {
    if (!formValid) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createCreditNote({
        invoice_id: invoiceId,
        reason: reason.trim() || undefined,
      });
      setCreateOpen(false);
      resetCreateForm();
      await loadCreditNotes();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to issue credit note.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDownload(creditNoteId: string, creditNoteNumber: string) {
    setError(null);
    try {
      await downloadCreditNotePdf(creditNoteId, creditNoteNumber);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download credit note PDF.");
    }
  }

  const invoiceIdByCreditNoteId = useMemo(
    () => Object.fromEntries(creditNotes.map((entry) => [entry.id, entry.invoice_id])),
    [creditNotes],
  );

  const rows: CreditNoteRow[] = creditNotes.map((entry) => ({
    id: entry.id,
    invoice_id: entry.invoice_id,
    credit_note_number: entry.credit_note_number,
    invoice_number: entry.invoice_number,
    issue_date: entry.issue_date,
    reason: entry.reason?.trim() || "—",
    subtotal_ex_vat: formatZarAmount(entry.subtotal_ex_vat),
    vat_amount: formatZarAmount(entry.vat_amount),
    total_inc_vat: formatZarAmount(entry.total_inc_vat),
    actions: entry.invoice_id,
  }));

  return (
    <Stack gap={6}>
      <div className="vellano-page-header">
        <div>
          <h1 className="cds--type-productive-heading-04">Credit notes</h1>
          <p className="cds--type-body-01">
            Reverse VAT and accounts receivable on a tax invoice. Credit notes are not emailed.
          </p>
        </div>
        {canMutate ? (
          <Button
            onClick={() => {
              resetCreateForm();
              setCreateOpen(true);
            }}
          >
            Issue credit note
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
        <p className="cds--type-body-01">Loading credit notes…</p>
      ) : creditNotes.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No credit notes"
          subtitle="No credit notes have been issued yet."
          hideCloseButton
          lowContrast
        />
      ) : (
        <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
          {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Credit notes" description="All Vellano credit notes">
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
                    const invoiceIdForRow = invoiceIdByCreditNoteId[row.id];
                    const creditNote = creditNotes.find((entry) => entry.id === row.id);
                    return (
                      <TableRow
                        {...getRowProps({ row })}
                        key={row.id}
                        onClick={() => {
                          if (invoiceIdForRow) {
                            router.push(`/invoices/${invoiceIdForRow}`);
                          }
                        }}
                        style={{ cursor: invoiceIdForRow ? "pointer" : undefined }}
                      >
                        {row.cells.map((cell) => {
                          if (cell.info.header === "actions") {
                            return (
                              <TableCell key={cell.id}>
                                <Stack gap={3} orientation="horizontal">
                                  <Button
                                    kind="ghost"
                                    size="sm"
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      if (invoiceIdForRow) {
                                        router.push(`/invoices/${invoiceIdForRow}`);
                                      }
                                    }}
                                  >
                                    View invoice
                                  </Button>
                                  <Button
                                    kind="ghost"
                                    size="sm"
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      if (creditNote) {
                                        void handleDownload(
                                          creditNote.id,
                                          creditNote.credit_note_number,
                                        );
                                      }
                                    }}
                                  >
                                    Download PDF
                                  </Button>
                                </Stack>
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
        modalHeading="Issue credit note"
        primaryButtonText={saving ? "Issuing…" : "Issue credit note"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || !formValid || availableInvoices.length === 0}
        onRequestClose={() => setCreateOpen(false)}
        onRequestSubmit={() => void handleCreate()}
      >
        <Stack gap={5}>
          {availableInvoices.length === 0 ? (
            <InlineNotification
              kind="info"
              title="No invoices available"
              subtitle="Every tax invoice already has a credit note, or no invoices exist yet."
              hideCloseButton
              lowContrast
            />
          ) : (
            <Select
              id="credit-note-invoice"
              labelText="Tax invoice"
              value={invoiceId}
              onChange={(event) => setInvoiceId(event.target.value)}
            >
              <SelectItem value="" text="Select an invoice" />
              {invoices.map((invoice) => {
                const hasCreditNote = creditedInvoiceIds.has(invoice.id);
                return (
                  <SelectItem
                    key={invoice.id}
                    value={invoice.id}
                    text={`${invoice.invoice_number} — ${invoice.customer_name}`}
                    disabled={hasCreditNote}
                  />
                );
              })}
            </Select>
          )}
          <TextArea
            id="credit-note-reason"
            labelText="Reason (optional)"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            rows={3}
          />
        </Stack>
      </Modal>
    </Stack>
  );
}

"use client";

import {
  Button,
  ComboBox,
  DataTable,
  InlineNotification,
  Modal,
  Pagination,
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
  canSendComms,
  createCreditNote,
  downloadCreditNotePdf,
  formatZarAmount,
  getCommsSettings,
  listCreditNotes,
  listInvoices,
  openCommsSend,
  sendDocument,
  type CreditNote,
  type InvoiceListItem,
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

export default function CreditNotesPage() {
  const router = useRouter();
  const { user } = useAuth();
  const canMutate = canMutateBooks(user);
  const canSend = canSendComms(user);
  const [creditNotes, setCreditNotes] = useState<CreditNote[]>([]);
  const [invoiceOptions, setInvoiceOptions] = useState<InvoiceOption[]>([]);
  const [creditedInvoiceIds, setCreditedInvoiceIds] = useState<Set<string>>(() => new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [invoiceId, setInvoiceId] = useState("");
  const [invoiceQuery, setInvoiceQuery] = useState("");
  const [debouncedInvoiceQuery, setDebouncedInvoiceQuery] = useState("");
  const [reason, setReason] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const [smtpConfigured, setSmtpConfigured] = useState(false);

  const loadCreditNotes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listCreditNotes({
        limit: pageSize,
        offset: (page - 1) * pageSize,
      });
      setCreditNotes(data.items);
      setTotal(data.total);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load credit notes.");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => {
    if (!user) {
      return;
    }
    void getCommsSettings()
      .then((comms) => setSmtpConfigured(comms.smtp_configured))
      .catch(() => setSmtpConfigured(false));
  }, [user]);

  useEffect(() => {
    if (user) {
      void loadCreditNotes();
    }
  }, [user, loadCreditNotes]);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedInvoiceQuery(invoiceQuery), 300);
    return () => clearTimeout(timer);
  }, [invoiceQuery]);

  useEffect(() => {
    if (!createOpen || !canMutate) {
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const [invoicePage, creditPage] = await Promise.all([
          listInvoices({ limit: 25, q: debouncedInvoiceQuery || undefined }),
          listCreditNotes({ limit: 100 }),
        ]);
        if (cancelled) {
          return;
        }
        setCreditedInvoiceIds(new Set(creditPage.items.map((entry) => entry.invoice_id)));
        setInvoiceOptions(
          invoicePage.items
            .filter((invoice) => !creditPage.items.some((cn) => cn.invoice_id === invoice.id))
            .map(invoiceToOption),
        );
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load invoices.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [createOpen, canMutate, debouncedInvoiceQuery]);

  const availableInvoices = useMemo(
    () => invoiceOptions.filter((option) => !creditedInvoiceIds.has(option.id)),
    [invoiceOptions, creditedInvoiceIds],
  );

  const selectedInvoiceOption = useMemo(
    () => availableInvoices.find((option) => option.id === invoiceId) ?? null,
    [availableInvoices, invoiceId],
  );

  const formValid = Boolean(invoiceId);

  function resetCreateForm() {
    setInvoiceId("");
    setInvoiceQuery("");
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

  async function handleEmail(creditNote: CreditNote) {
    setError(null);
    try {
      await sendDocument("credit-notes", creditNote.id, "email");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to email credit note.");
    }
  }

  async function handleWhatsApp(creditNote: CreditNote) {
    setError(null);
    try {
      openCommsSend(await sendDocument("credit-notes", creditNote.id, "whatsapp"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to open WhatsApp.");
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
      <div className="firstout-page-header">
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
      ) : total === 0 ? (
        <InlineNotification
          kind="info"
          title="No credit notes"
          subtitle="No credit notes have been issued yet."
          hideCloseButton
          lowContrast
        />
      ) : (
        <>
          <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
            {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
              <TableContainer title="Credit notes" description="All Firstout credit notes">
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
                                    {canSend ? (
                                      <Button
                                        kind="ghost"
                                        size="sm"
                                        disabled={!creditNote?.customer_email || !smtpConfigured}
                                        onClick={(event) => {
                                          event.stopPropagation();
                                          if (creditNote) {
                                            void handleEmail(creditNote);
                                          }
                                        }}
                                      >
                                        Email
                                      </Button>
                                    ) : null}
                                    {canSend ? (
                                      <Button
                                        kind="ghost"
                                        size="sm"
                                        disabled={!creditNote?.customer_whatsapp_e164}
                                        onClick={(event) => {
                                          event.stopPropagation();
                                          if (creditNote) {
                                            void handleWhatsApp(creditNote);
                                          }
                                        }}
                                      >
                                        WhatsApp
                                      </Button>
                                    ) : null}
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
              subtitle="Every tax invoice already has a credit note, or no invoices match your search."
              hideCloseButton
              lowContrast
            />
          ) : (
            <ComboBox
              id="credit-note-invoice"
              titleText="Tax invoice"
              placeholder="Search invoice number or customer…"
              items={availableInvoices}
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

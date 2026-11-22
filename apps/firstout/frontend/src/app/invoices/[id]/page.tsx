"use client";

import { LoadingField, LoadingRegion, LoadingTableRows } from "@/components/page-loading";
import { StaffImage } from "@/components/staff-image";

import {
  Button,
  InlineNotification,
  Modal,
  OverflowMenu,
  OverflowMenuItem,
  Select,
  SelectItem,
  SkeletonText,
  Stack,
  Tag,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  TextArea,
  TextInput,
} from "@carbon/react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";

import { ArchiveInvoiceModal } from "@/components/archive-invoice-modal";
import { BooksHistory } from "@/components/books-history";
import { PaymentMethodFields, paymentMethodLabel } from "@/components/payment-method-fields";
import {
  INVOICE_NOTE_MAX,
  canMutateBooks,
  createCreditNote,
  createPayment,
  downloadInvoicePdf,
  exVatToIncVat,
  formatPriceAmount,
  formatZarAmount,
  getCustomer,
  getInvoice,
  getSettings,
  invoiceAction,
  settingsLogoUrl,
  listCreditNotes,
  updateInvoiceNote,
  updateInvoiceSalesStaff,
  listPayments,
  type AppSettings,
  type CreditNote,
  type CustomerCrm,
  type Invoice,
  type Payment,
  type PaymentMethod,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { referenceQueries } from "@/lib/queries";
import { localIsoDate } from "@/lib/dates";
import { formatArchiveCurrency, formatSettlementAmount } from "@/lib/source-history";
import { invoiceStatusTag, partialPaymentError } from "@/lib/payment-status";

function hasPositiveBalance(balance: string): boolean {
  return Number(balance) > 0;
}

export default function InvoiceDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  // The invoices list opens Record payment or Issue credit note here with ?action=.
  const requestedAction = useSearchParams().get("action");
  const { user } = useAuth();
  const canMutate = canMutateBooks(user);
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [companySettings, setCompanySettings] = useState<AppSettings | null>(null);
  const [customer, setCustomer] = useState<CustomerCrm | null>(null);
  const [creditNote, setCreditNote] = useState<CreditNote | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [paymentOpen, setPaymentOpen] = useState(false);
  const [paymentAmount, setPaymentAmount] = useState("");
  const [paymentDate, setPaymentDate] = useState(localIsoDate());
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("eft");
  const [paymentReference, setPaymentReference] = useState("");
  const [creditOpen, setCreditOpen] = useState(false);
  const [creditReason, setCreditReason] = useState("");
  const [lastPayment, setLastPayment] = useState<Payment | null>(null);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [noteDraft, setNoteDraft] = useState("");
  const [noteSaving, setNoteSaving] = useState(false);
  const colleagues = useQuery({ ...referenceQueries.salesStaffOptions, enabled: canMutate }).data ?? null;
  const [colleagueSaving, setColleagueSaving] = useState(false);
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [actionHandled, setActionHandled] = useState(false);

  const loadInvoice = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const invoiceData = await getInvoice(params.id);
      setNoteDraft(invoiceData.note_internal ?? "");
      if (invoiceData.is_archive) {
        setInvoice(invoiceData);
        setCustomer(null);
        setPayments([]);
        setCreditNote(null);
        setCompanySettings(null);
        return;
      }
      const [crmCustomer, creditNotePage, settingsData, paymentPage] = await Promise.all([
        getCustomer(invoiceData.customer_id),
        listCreditNotes({ limit: 100 }),
        getSettings(),
        listPayments({ invoice_id: invoiceData.id, limit: 100 }),
      ]);
      setInvoice(invoiceData);
      setPayments(paymentPage.items);
      setCompanySettings(settingsData);
      setCustomer(crmCustomer);
      setCreditNote(
        creditNotePage.items.find((entry) => entry.invoice_id === invoiceData.id) ?? null,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load invoice.");
    } finally {
      setLoading(false);
    }
  }, [params.id]);

  useEffect(() => {
    if (user && params.id) {
      void loadInvoice();
    }
  }, [user, params.id, loadInvoice]);


  async function handleDownload() {
    if (!invoice || invoice.is_archive) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await downloadInvoicePdf(invoice.id, invoice.invoice_number);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download tax invoice.");
    } finally {
      setActionLoading(false);
    }
  }


  function openPaymentModal() {
    if (!invoice || invoice.is_archive) {
      return;
    }
    setPaymentAmount(invoice.balance);
    setPaymentDate(localIsoDate());
    setPaymentReference("");
    setPaymentOpen(true);
  }

  async function handleRecordPayment() {
    if (!invoice || invoice.is_archive) {
      return;
    }
    const validationError = partialPaymentError({
      amount: paymentAmount,
      balance: invoice.balance,
      documentNumber: invoice.invoice_number,
    });
    if (validationError) {
      setError(validationError);
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const payment = await createPayment({
        direction: "in",
        invoice_id: invoice.id,
        amount: paymentAmount.trim(),
        currency: "ZAR",
        paid_on: paymentDate,
        tender: paymentMethod,
        reference: paymentReference.trim() || undefined,
      });
      setLastPayment(payment);
      setPaymentOpen(false);
      setSuccess(`Payment ${payment.payment_number} recorded.`);
      await loadInvoice();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to record payment.");
    } finally {
      setActionLoading(false);
    }
  }

  useEffect(() => {
    if (actionHandled || !invoice || invoice.is_archive || !canMutate) return;
    setActionHandled(true);
    if (requestedAction === "pay" && hasPositiveBalance(invoice.balance)) {
      setPaymentAmount(invoice.balance);
      setPaymentDate(localIsoDate());
      setPaymentReference("");
      setPaymentOpen(true);
    } else if (requestedAction === "credit" && !creditNote) {
      setCreditOpen(true);
    }
  }, [actionHandled, canMutate, creditNote, invoice, requestedAction]);

  async function handleArchive(archived: boolean) {
    if (!invoice) return;
    setArchiveOpen(false);
    setActionLoading(true);
    setError(null);
    try {
      const saved = await invoiceAction(invoice.id, archived ? "archive" : "restore");
      setInvoice(saved);
      setSuccess(
        archived
          ? `${saved.invoice_number} archived. It still counts in the books, VAT and reports.`
          : `${saved.invoice_number} restored to the active list.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to change the invoice.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleSalesColleague(staffId: string) {
    if (!invoice) return;
    setColleagueSaving(true);
    setError(null);
    try {
      const saved = await updateInvoiceSalesStaff(invoice.id, staffId || null);
      setInvoice(saved);
      setSuccess(
        saved.sales_staff_name
          ? `Commission on ${saved.invoice_number} now goes to ${saved.sales_staff_name}.`
          : `${saved.invoice_number} no longer has a sales colleague.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to change the sales colleague.");
    } finally {
      setColleagueSaving(false);
    }
  }

  async function handleSaveNote() {
    if (!invoice) {
      return;
    }
    setNoteSaving(true);
    setError(null);
    try {
      const saved = await updateInvoiceNote(invoice.id, noteDraft.trim());
      setInvoice(saved);
      setNoteDraft(saved.note_internal ?? "");
      setSuccess("Internal note saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save the internal note.");
    } finally {
      setNoteSaving(false);
    }
  }

  async function handleIssueCreditNote() {
    if (!invoice || invoice.is_archive) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const created = await createCreditNote({
        invoice_id: invoice.id,
        reason: creditReason.trim() || undefined,
      });
      setCreditOpen(false);
      setCreditReason("");
      setSuccess(`Credit note ${created.credit_note_number} issued.`);
      await loadInvoice();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to issue credit note.");
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) {
    return (
      <Stack gap={6}>
        <div style={{ alignSelf: "flex-start" }}>
          <Button kind="ghost" size="sm" onClick={() => router.push("/invoices")}>← Back to invoices</Button>
        </div>
        <LoadingRegion label="Loading invoice…">
          <Stack gap={6}>
            <div aria-hidden="true">
              <SkeletonText heading width="14rem" />
              <SkeletonText width="min(24rem, 85%)" />
              <SkeletonText width="5rem" />
            </div>
            <Stack gap={4} orientation="horizontal" aria-hidden="true">
              <LoadingField width="9rem" height="3rem" />
              <LoadingField width="8rem" height="3rem" />
              {canMutate && <LoadingField width="10rem" height="3rem" />}
            </Stack>
            <section className="firstout-tax-invoice">
              <div className="firstout-tax-invoice__header" aria-hidden="true">
                <SkeletonText heading width="10rem" />
                <SkeletonText paragraph lineCount={2} width="9rem" />
              </div>
              <div className="firstout-tax-invoice__parties">
                {["Seller", "Buyer"].map((party) => (
                  <div key={party}>
                    <p className="cds--type-label-01">{party}</p>
                    <SkeletonText paragraph lineCount={3} width="75%" />
                  </div>
                ))}
              </div>
              <TableContainer title="Line items">
                <LoadingTableRows columns={["Description", "Qty", "Unit", "Ex VAT", "VAT", "Inc VAT"]} />
              </TableContainer>
              <div className="firstout-tax-invoice__totals" aria-hidden="true">
                <SkeletonText paragraph lineCount={3} width="10rem" />
              </div>
            </section>
            <TableContainer title="Payments" description="Money received against this invoice">
              <LoadingTableRows columns={["Number", "Paid on", "Amount", "Reconciled"]} rows={2} />
            </TableContainer>
          </Stack>
        </LoadingRegion>
      </Stack>
    );
  }

  if (!invoice) {
    return (
      <InlineNotification
        kind="error"
        title="Not found"
        subtitle="Invoice could not be loaded."
        hideCloseButton
        lowContrast
      />
    );
  }

  const showPayment = !invoice.is_archive && canMutate && hasPositiveBalance(invoice.balance);
  const showCreditNote = !invoice.is_archive && canMutate && !creditNote;
  const statusTag = invoiceStatusTag(invoice);
  const formatInvoiceAmount = invoice.is_archive ? formatArchiveCurrency : formatZarAmount;
  const canEditNote = !invoice.is_archive && canMutate;
  const noteChanged = noteDraft.trim() !== (invoice.note_internal ?? "");

  return (
    <Stack gap={6}>
      <div>
        <Button kind="ghost" size="sm" onClick={() => router.push("/invoices")}>
          ← Back to invoices
        </Button>
        <h1 className="cds--type-productive-heading-04" style={{ marginTop: "0.5rem" }}>
          {invoice.invoice_number}
        </h1>
        <p className="cds--type-body-01">
          {invoice.customer_name} · Issued {invoice.issue_date}
        </p>
        <Tag type={statusTag.type} size="sm">
          {statusTag.label}
        </Tag>
        {invoice.is_archived ? (
          <Tag type="outline" size="sm">
            Archived
          </Tag>
        ) : null}
      </div>

      {invoice.is_archived ? (
        <InlineNotification
          kind="info"
          title="Archived"
          subtitle="Hidden from the default list. It still counts in the books, VAT and reports."
          hideCloseButton
          lowContrast
        />
      ) : null}

      {invoice.is_archive ? (
        <InlineNotification
          kind="info"
          title="Imported history; payments and opening balances were not imported"
          subtitle="This invoice is read-only. Source totals are preserved; payment status and balances are not imported."
          hideCloseButton
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

      {error ? (
        <InlineNotification
          kind="error"
          title="Error"
          subtitle={error}
          onCloseButtonClick={() => setError(null)}
          lowContrast
        />
      ) : null}

      {!invoice.is_archive ? <Stack gap={4} orientation="horizontal">
        <Button kind="secondary" disabled={actionLoading} onClick={() => void handleDownload()}>
          Download tax invoice
        </Button>
        {showPayment ? (
          <Button disabled={actionLoading} onClick={openPaymentModal}>
            Record payment in
          </Button>
        ) : null}
        {showCreditNote ? (
          <Button kind="tertiary" disabled={actionLoading} onClick={() => setCreditOpen(true)}>
            Issue credit note
          </Button>
        ) : null}
        {canMutate ? (
          <OverflowMenu aria-label="More invoice actions" iconDescription="More invoice actions" flipped size="lg">
            {invoice.is_archived ? (
              <OverflowMenuItem itemText="Restore" disabled={actionLoading} onClick={() => void handleArchive(false)} />
            ) : (
              <OverflowMenuItem itemText="Archive" disabled={actionLoading} onClick={() => setArchiveOpen(true)} />
            )}
          </OverflowMenu>
        ) : null}
      </Stack> : null}

      <ArchiveInvoiceModal
        invoiceNumber={archiveOpen ? invoice.invoice_number : null}
        onClose={() => setArchiveOpen(false)}
        onConfirm={() => void handleArchive(true)}
      />

      {!invoice.is_archive && creditNote ? (
        <Stack gap={3}>
          <InlineNotification
            kind="info"
            title="Credit note"
            subtitle={`${creditNote.credit_note_number} issued on ${creditNote.issue_date}.`}
            hideCloseButton
            lowContrast
          />
          <div>
            <Button kind="ghost" size="sm" onClick={() => router.push("/credit-notes")}>
              View credit notes
            </Button>
          </div>
        </Stack>
      ) : null}

      <section className="firstout-tax-invoice">
        <div className="firstout-tax-invoice__header">
          <div>
            <p className="cds--type-productive-heading-03">{invoice.is_archive ? "Imported invoice history" : "Tax invoice"}</p>
            <p className="cds--type-body-01">{invoice.invoice_number}</p>
            <p className="cds--type-body-01">Issue date: {invoice.issue_date}</p>
            {!invoice.is_archive && invoice.due_date ? (
              <p className="cds--type-body-01">Due date: {invoice.due_date}</p>
            ) : null}
          </div>
        </div>
        <div className="firstout-tax-invoice__parties">
          {!invoice.is_archive ? <div>
            <p className="cds--type-label-01">Seller</p>
            {companySettings?.has_logo ? (
              <StaffImage className="firstout-company-logo" src={settingsLogoUrl()} alt="" />
            ) : null}
            <p className="cds--type-body-01">{companySettings?.legal_name ?? "—"}</p>
            <p className="cds--type-body-01">{companySettings?.address ?? "—"}</p>
            <p className="cds--type-body-01">
              VAT {companySettings?.vat_number ?? "—"}
            </p>
          </div> : null}
          <div>
            <p className="cds--type-label-01">Buyer</p>
            <p className="cds--type-body-01">{invoice.customer_name}</p>
            {customer?.billing_address ? (
              <p className="cds--type-body-01">{customer.billing_address}</p>
            ) : null}
            {customer?.vat_number ? (
              <p className="cds--type-body-01">VAT {customer.vat_number}</p>
            ) : null}
            {customer?.email ? <p className="cds--type-body-01">{customer.email}</p> : null}
          </div>
        </div>
        <TableContainer title="Line items">
          <Table>
            <TableHead>
              <TableRow>
                <TableHeader>Description</TableHeader>
                <TableHeader>Qty</TableHeader>
                {!invoice.is_archive ? <TableHeader>
                  {invoice.prices_include_vat ? "Unit incl. VAT" : "Unit excl. VAT"}
                </TableHeader> : null}
                <TableHeader>Ex VAT</TableHeader>
                <TableHeader>{invoice.is_archive ? "VAT" : `VAT (${companySettings?.vat_percent ?? "15"}%)`}</TableHeader>
                <TableHeader>Inc VAT</TableHeader>
              </TableRow>
            </TableHead>
            <TableBody>
              {invoice.lines.map((line) => (
                <TableRow key={line.id}>
                  <TableCell>
                    {line.description}
                    {!invoice.is_archive && line.price_warning ? (
                      <div className="firstout-muted-text">{line.price_warning}</div>
                    ) : null}
                    {!invoice.is_archive && line.suspect_price_warning ? (
                      <div className="firstout-price-warning">{line.suspect_price_warning}</div>
                    ) : null}
                  </TableCell>
                  <TableCell>{line.qty}</TableCell>
                  {!invoice.is_archive ? <TableCell>
                    {formatZarAmount(
                      invoice.prices_include_vat
                        ? formatPriceAmount(exVatToIncVat(Number(line.unit_ex_vat)))
                        : line.unit_ex_vat,
                    )}
                  </TableCell> : null}
                  <TableCell>{formatInvoiceAmount(line.ex_vat)}</TableCell>
                  <TableCell>{formatInvoiceAmount(line.vat_amount)}</TableCell>
                  <TableCell>{formatInvoiceAmount(line.inc_vat)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
        <div className="firstout-tax-invoice__totals">
          <p className="cds--type-body-01">
            Subtotal ex VAT: {formatInvoiceAmount(invoice.subtotal_ex_vat)}
          </p>
          <p className="cds--type-body-01">
            {invoice.is_archive ? "VAT" : `VAT (${companySettings?.vat_percent ?? "15"}%)`}: {formatInvoiceAmount(invoice.vat_amount)}
          </p>
          <p className="cds--type-productive-heading-02">
            Total: {formatInvoiceAmount(invoice.total_inc_vat)}
          </p>
          <p className="cds--type-body-01">Paid: {formatSettlementAmount(invoice.amount_paid, invoice.is_archive)}</p>
          <p className="cds--type-body-01">
            Balance owing: {formatSettlementAmount(invoice.balance, invoice.is_archive)}
          </p>
        </div>
        {invoice.note_printed ? (
          <div>
            <p className="cds--type-label-01">Note</p>
            <p className="cds--type-body-01" style={{ whiteSpace: "pre-wrap" }}>{invoice.note_printed}</p>
          </div>
        ) : null}
      </section>

      {canEditNote && colleagues ? (
        <div style={{ maxWidth: "20rem" }}>
          <Select
            id="invoice-sales-colleague"
            labelText="Sales colleague"
            helperText="Who made this sale. Their commission counts it."
            value={invoice.sales_staff_id ?? ""}
            disabled={colleagueSaving}
            onChange={(event) => void handleSalesColleague(event.target.value)}
          >
            <SelectItem value="" text="No colleague (unattributed)" />
            {invoice.sales_staff_id && !colleagues.some((item) => item.id === invoice.sales_staff_id) ? (
              <SelectItem value={invoice.sales_staff_id} text={`${invoice.sales_staff_name ?? "Colleague"} (inactive)`} />
            ) : null}
            {colleagues.map((item) => <SelectItem key={item.id} value={item.id} text={item.name} />)}
          </Select>
        </div>
      ) : invoice.sales_staff_name ? (
        <div>
          <p className="cds--type-label-01">Sales colleague</p>
          <p className="cds--type-body-01">{invoice.sales_staff_name}</p>
        </div>
      ) : null}

      {canEditNote ? (
        <Stack gap={3}>
          <TextArea
            id="invoice-note-internal"
            labelText="Internal note"
            helperText="Staff only. Never printed."
            rows={3}
            maxCount={INVOICE_NOTE_MAX}
            enableCounter
            value={noteDraft}
            onChange={(event) => setNoteDraft(event.target.value)}
          />
          {noteChanged ? (
            <Stack gap={3} orientation="horizontal">
              <Button size="sm" disabled={noteSaving} onClick={() => void handleSaveNote()}>
                {noteSaving ? "Saving…" : "Save note"}
              </Button>
              <Button
                size="sm"
                kind="ghost"
                disabled={noteSaving}
                onClick={() => setNoteDraft(invoice.note_internal ?? "")}
              >
                Cancel
              </Button>
            </Stack>
          ) : null}
        </Stack>
      ) : invoice.note_internal ? (
        <div>
          <p className="cds--type-label-01">Internal note</p>
          <p className="cds--type-body-01" style={{ whiteSpace: "pre-wrap" }}>{invoice.note_internal}</p>
          <p className="cds--type-helper-text-01">Staff only. Never printed.</p>
        </div>
      ) : null}

      {invoice.is_archive ? <p className="cds--type-body-01">Payments: Not imported</p> : <TableContainer title="Payments" description="Money received against this invoice">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeader>Number</TableHeader>
              <TableHeader>Paid on</TableHeader>
              <TableHeader>Amount</TableHeader>
              <TableHeader>Method</TableHeader>
              <TableHeader>Reference</TableHeader>
              <TableHeader>Reconciled</TableHeader>
            </TableRow>
          </TableHead>
          <TableBody>
            {payments.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6}>No payments recorded yet.</TableCell>
              </TableRow>
            ) : (
              payments.map((payment) => (
                <TableRow key={payment.id}>
                  <TableCell>{payment.payment_number}</TableCell>
                  <TableCell>{payment.paid_on}</TableCell>
                  <TableCell>{formatZarAmount(payment.amount)}</TableCell>
                  <TableCell>{paymentMethodLabel(payment.tender)}</TableCell>
                  <TableCell>{payment.reference ?? "—"}</TableCell>
                  <TableCell>{payment.is_voided ? "Voided" : payment.is_reconciled ? "Yes" : "No"}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>}

      <BooksHistory key={invoice.sales_staff_id ?? ""} documentType="invoice" documentId={invoice.id} />

      {!invoice.is_archive ? <Modal
        open={paymentOpen}
        modalHeading="Record payment in"
        primaryButtonText={actionLoading ? "Recording…" : "Record payment"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={actionLoading || !paymentAmount.trim() || !paymentDate}
        onRequestClose={() => setPaymentOpen(false)}
        onRequestSubmit={() => void handleRecordPayment()}
      >
        <Stack gap={5}>
          <TextInput
            id="payment-amount"
            labelText="Amount (ZAR)"
            helperText={`Any amount up to the ${formatZarAmount(invoice.balance)} still owing. A smaller amount leaves the invoice partially paid.`}
            value={paymentAmount}
            onChange={(event) => setPaymentAmount(event.target.value)}
            required
          />
          <TextInput
            id="payment-date"
            labelText="Paid on"
            type="date"
            value={paymentDate}
            onChange={(event) => setPaymentDate(event.target.value)}
            required
          />
          <PaymentMethodFields
            idPrefix="invoice-payment"
            method={paymentMethod}
            reference={paymentReference}
            onMethodChange={setPaymentMethod}
            onReferenceChange={setPaymentReference}
          />
        </Stack>
      </Modal> : null}

      {!invoice.is_archive ? <Modal
        open={creditOpen}
        modalHeading="Issue credit note"
        primaryButtonText={actionLoading ? "Issuing…" : "Issue credit note"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={actionLoading}
        onRequestClose={() => setCreditOpen(false)}
        onRequestSubmit={() => void handleIssueCreditNote()}
      >
        <TextArea
          id="credit-reason"
          labelText="Reason (optional)"
          value={creditReason}
          onChange={(event) => setCreditReason(event.target.value)}
          rows={3}
        />
      </Modal> : null}

      {!invoice.is_archive && lastPayment ? (
        <InlineNotification
          kind="info"
          title="Last payment"
          subtitle={`${lastPayment.payment_number} — ${formatZarAmount(lastPayment.amount_zar)} on ${lastPayment.paid_on}.`}
          hideCloseButton
          lowContrast
        />
      ) : null}
    </Stack>
  );
}

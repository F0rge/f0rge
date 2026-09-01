"use client";

import {
  Button,
  InlineNotification,
  Modal,
  Stack,
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
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  canMutateBooks,
  createCreditNote,
  createPayment,
  downloadInvoicePdf,
  formatZarAmount,
  getInvoice,
  listContacts,
  listCreditNotes,
  type Contact,
  type CreditNote,
  type Invoice,
  type Payment,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const SELLER = {
  name: "Vellano",
  address: "Kramerville, Johannesburg, South Africa",
  vat: "4123456789",
};

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function hasPositiveBalance(balance: string): boolean {
  return Number(balance) > 0;
}

export default function InvoiceDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const canMutate = canMutateBooks(user?.role);
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [customer, setCustomer] = useState<Contact | null>(null);
  const [creditNote, setCreditNote] = useState<CreditNote | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [paymentOpen, setPaymentOpen] = useState(false);
  const [paymentAmount, setPaymentAmount] = useState("");
  const [paymentDate, setPaymentDate] = useState(todayIso());
  const [creditOpen, setCreditOpen] = useState(false);
  const [creditReason, setCreditReason] = useState("");
  const [lastPayment, setLastPayment] = useState<Payment | null>(null);

  const loadInvoice = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [invoiceData, contacts, creditNotes] = await Promise.all([
        getInvoice(params.id),
        listContacts(),
        listCreditNotes(),
      ]);
      setInvoice(invoiceData);
      setCustomer(contacts.find((entry) => entry.id === invoiceData.customer_id) ?? null);
      setCreditNote(creditNotes.find((entry) => entry.invoice_id === invoiceData.id) ?? null);
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
    if (!invoice) {
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
    if (!invoice) {
      return;
    }
    setPaymentAmount(invoice.balance);
    setPaymentDate(todayIso());
    setPaymentOpen(true);
  }

  async function handleRecordPayment() {
    if (!invoice) {
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

  async function handleIssueCreditNote() {
    if (!invoice) {
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
    return <p className="cds--type-body-01">Loading invoice…</p>;
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

  const showPayment = canMutate && hasPositiveBalance(invoice.balance);
  const showCreditNote = canMutate && !creditNote;

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
      </div>

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

      <Stack gap={4} orientation="horizontal">
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
      </Stack>

      {creditNote ? (
        <InlineNotification
          kind="info"
          title="Credit note"
          subtitle={`${creditNote.credit_note_number} issued on ${creditNote.issue_date}.`}
          hideCloseButton
          lowContrast
        />
      ) : null}

      <section className="vellano-tax-invoice">
        <div className="vellano-tax-invoice__header">
          <div>
            <p className="cds--type-productive-heading-03">Tax invoice</p>
            <p className="cds--type-body-01">{invoice.invoice_number}</p>
            <p className="cds--type-body-01">Issue date: {invoice.issue_date}</p>
          </div>
        </div>
        <div className="vellano-tax-invoice__parties">
          <div>
            <p className="cds--type-label-01">Seller</p>
            <p className="cds--type-body-01">{SELLER.name}</p>
            <p className="cds--type-body-01">{SELLER.address}</p>
            <p className="cds--type-body-01">VAT {SELLER.vat}</p>
          </div>
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
                <TableHeader>Unit ex VAT</TableHeader>
                <TableHeader>Ex VAT</TableHeader>
                <TableHeader>VAT (15%)</TableHeader>
                <TableHeader>Inc VAT</TableHeader>
              </TableRow>
            </TableHead>
            <TableBody>
              {invoice.lines.map((line) => (
                <TableRow key={line.id}>
                  <TableCell>{line.description}</TableCell>
                  <TableCell>{line.qty}</TableCell>
                  <TableCell>{formatZarAmount(line.unit_ex_vat)}</TableCell>
                  <TableCell>{formatZarAmount(line.ex_vat)}</TableCell>
                  <TableCell>{formatZarAmount(line.vat_amount)}</TableCell>
                  <TableCell>{formatZarAmount(line.inc_vat)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
        <div className="vellano-tax-invoice__totals">
          <p className="cds--type-body-01">
            Subtotal ex VAT: {formatZarAmount(invoice.subtotal_ex_vat)}
          </p>
          <p className="cds--type-body-01">VAT (15%): {formatZarAmount(invoice.vat_amount)}</p>
          <p className="cds--type-productive-heading-02">
            Total inc VAT: {formatZarAmount(invoice.total_inc_vat)}
          </p>
          <p className="cds--type-body-01">Amount paid: {formatZarAmount(invoice.amount_paid)}</p>
          <p className="cds--type-body-01">Balance due: {formatZarAmount(invoice.balance)}</p>
        </div>
      </section>

      <Modal
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
            helperText="Must equal the remaining invoice balance."
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
        </Stack>
      </Modal>

      <Modal
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
      </Modal>

      {lastPayment ? (
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

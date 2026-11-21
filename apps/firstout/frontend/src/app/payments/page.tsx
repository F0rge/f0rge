"use client";

import {
  Button,
  InlineNotification,
  Modal,
  RadioButton,
  RadioButtonGroup,
  Select,
  SelectItem,
  Stack,
  Tag,
  TextArea,
  TextInput,
} from "@carbon/react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { BooksHistory } from "@/components/books-history";
import { KpiStrip } from "@/components/kpi-strip";
import { PaymentMethodFields, paymentMethodLabel } from "@/components/payment-method-fields";
import {
  RecordDetail,
  RecordDetails,
  RecordWorkspace,
  type RecordWorkspaceAdapter,
} from "@/components/record-workspace";
import {
  canMutateBooks,
  createPayment,
  downloadPaymentPdf,
  formatFxGainLoss,
  formatZarAmount,
  getPaymentSummary,
  listOpenPaymentDocuments,
  voidPayment,
  type Payment,
  type PaymentDirection,
  type PaymentMethod,
  type PaymentOpenDocument,
  type PaymentSummary,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { partialPaymentError } from "@/lib/payment-status";
import { workspaceIdentity } from "@/lib/record-workspace";
import { localIsoDate } from "@/lib/till-statement";

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

function documentHref(payment: Payment): string | null {
  if (payment.invoice_id) return `/invoices/${payment.invoice_id}`;
  if (payment.bill_id) return `/bills/${payment.bill_id}`;
  return null;
}

function PaymentStatusTag({ payment }: { payment: Payment }) {
  if (payment.is_voided) return <Tag type="red" size="sm">Voided</Tag>;
  if (payment.is_reconciled) return <Tag type="green" size="sm">Reconciled</Tag>;
  return <Tag type="outline" size="sm">Unreconciled</Tag>;
}

function AgainstLink({ payment }: { payment: Payment }) {
  const href = documentHref(payment);
  return href ? <Link href={href}>{payment.document_number ?? "Open"}</Link> : <>—</>;
}

const adapter = {
  resource: "payments",
  title: "Payments",
  singular: "payment",
  breadcrumb: "Books",
  description: "Recorded cash movements. Record a payment here or from an invoice or bill.",
  defaultSort: "-paid_on",
  lifecycle: { activeLabel: "Active", archivedLabel: "Voided" },
  columns: [
    { key: "payment_number", label: "Number", sortable: true, render: (item) => item.payment_number },
    { key: "direction", label: "Direction", render: (item) => (item.direction === "in" ? "In" : "Out") },
    { key: "party_name", label: "Party", sortable: true, render: (item) => item.party_name ?? "—" },
    { key: "document_number", label: "Against", sortable: true, render: (item) => <AgainstLink payment={item} /> },
    { key: "amount", label: "Amount", numeric: true, sortable: true, render: (item) => item.amount },
    { key: "currency", label: "Currency", render: (item) => item.currency },
    { key: "amount_zar", label: "ZAR", numeric: true, sortable: true, render: (item) => formatZarAmount(item.amount_zar) },
    { key: "fx_gain_loss_zar", label: "FX gain/loss", numeric: true, render: (item) => formatFxGainLoss(item.fx_gain_loss_zar) },
    { key: "paid_on", label: "Paid on", sortable: true, render: (item) => item.paid_on },
    { key: "tender", label: "Method", render: (item) => paymentMethodLabel(item.tender) },
    { key: "reference", label: "Reference", render: (item) => item.reference ?? "—" },
    { key: "is_reconciled", label: "Reconciled", render: (item) => <PaymentStatusTag payment={item} /> },
  ],
  filters: [
    {
      key: "direction",
      label: "Direction",
      type: "enum",
      quick: true,
      allLabel: "All directions",
      options: [
        { value: "in", label: "In" },
        { value: "out", label: "Out" },
      ],
    },
    {
      key: "tender",
      label: "Method",
      type: "enum",
      quick: true,
      allLabel: "All methods",
      options: [
        { value: "eft", label: "EFT" },
        { value: "card", label: "Card" },
        { value: "cash", label: "Cash" },
        { value: "other", label: "Other" },
        { value: "deposit", label: "Deposit" },
      ],
    },
    { key: "is_reconciled", label: "Reconciled", type: "boolean", quick: true, allLabel: "Any" },
    { key: "party_name", label: "Party", type: "text" },
    { key: "reference", label: "Reference", type: "text" },
    { key: "paid_on", label: "Paid on", type: "date" },
    { key: "amount_zar", label: "ZAR", type: "number" },
  ],
  getTitle: (item) => item.payment_number,
  getSubtitle: (item) =>
    [item.direction === "in" ? "Received" : "Paid", item.party_name].filter(Boolean).join(" · "),
} satisfies RecordWorkspaceAdapter<Payment>;

export default function PaymentsPage() {
  const { user } = useAuth();
  return <PaymentsContent key={workspaceIdentity(user)} />;
}

function PaymentsContent() {
  const { user } = useAuth();
  const canMutate = canMutateBooks(user);
  const [refreshKey, setRefreshKey] = useState(0);
  const [summary, setSummary] = useState<PaymentSummary | null | undefined>();
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [recording, setRecording] = useState(false);
  const [voiding, setVoiding] = useState<Payment | null>(null);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    getPaymentSummary()
      .then((data) => {
        if (!cancelled) setSummary(data);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setSummary(null);
        setError(err instanceof Error ? err.message : "Failed to load payment totals.");
      });
    return () => {
      cancelled = true;
    };
  }, [user, refreshKey]);

  function changed(message: string) {
    setNotice(message);
    setRefreshKey((value) => value + 1);
  }

  async function handleDownload(payment: Payment) {
    setError(null);
    try {
      await downloadPaymentPdf(payment.id, payment.payment_number);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download payment receipt.");
    }
  }

  return (
    <Stack gap={6}>
      {error ? (
        <InlineNotification kind="error" title="Error" subtitle={error} onCloseButtonClick={() => setError(null)} lowContrast />
      ) : null}
      {notice ? (
        <InlineNotification kind="success" title="Done" subtitle={notice} onCloseButtonClick={() => setNotice(null)} lowContrast />
      ) : null}

      <RecordWorkspace<Payment>
        adapter={adapter}
        refreshKey={refreshKey}
        onCreate={canMutate ? () => setRecording(true) : undefined}
        createLabel="Record payment"
        summary={
          <KpiStrip
            label="Payment totals"
            count={3}
            items={
              summary && [
                {
                  label: "Received this month",
                  value: formatZarAmount(summary.received_this_month_zar),
                  sub: plural(summary.received_this_month_count, "payment"),
                },
                {
                  label: "Paid out this month",
                  value: formatZarAmount(summary.paid_this_month_zar),
                  sub: plural(summary.paid_this_month_count, "payment"),
                },
                {
                  label: "Unreconciled",
                  value: String(summary.unreconciled_count),
                  sub: `${formatZarAmount(summary.unreconciled_net_zar)} net`,
                  warn: summary.unreconciled_count > 0,
                },
              ]
            }
          />
        }
        renderDetails={(item) => {
          const href = documentHref(item);
          return (
            <Stack gap={5}>
              {item.is_voided ? (
                <InlineNotification
                  kind="warning"
                  title="Voided"
                  subtitle={`${item.voided_at?.slice(0, 10) ?? ""}. ${item.void_reason ?? ""}`}
                  hideCloseButton
                  lowContrast
                />
              ) : null}
              <RecordDetails>
                <RecordDetail label="Direction">
                  {item.direction === "in" ? "Received from a customer" : "Paid to a supplier"}
                </RecordDetail>
                <RecordDetail label={item.direction === "in" ? "Customer" : "Supplier"}>{item.party_name}</RecordDetail>
                <RecordDetail label="Against"><AgainstLink payment={item} /></RecordDetail>
                <RecordDetail label="Paid on">{item.paid_on}</RecordDetail>
                <RecordDetail label="Method">{paymentMethodLabel(item.tender)}</RecordDetail>
                <RecordDetail label="Reference">{item.reference}</RecordDetail>
                <RecordDetail label="Amount">
                  {item.currency} {item.amount}
                  {item.currency !== "ZAR" ? ` (${formatZarAmount(item.amount_zar)} at ${item.fx_to_zar})` : ""}
                </RecordDetail>
                <RecordDetail label="Status"><PaymentStatusTag payment={item} /></RecordDetail>
              </RecordDetails>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                <Button kind="tertiary" size="sm" onClick={() => void handleDownload(item)}>
                  Download receipt
                </Button>
                {href ? (
                  <Button kind="ghost" size="sm" href={href}>
                    Open {item.invoice_id ? "invoice" : "bill"}
                  </Button>
                ) : null}
                {canMutate && !item.is_voided ? (
                  <Button
                    kind="danger--tertiary"
                    size="sm"
                    disabled={item.is_reconciled}
                    title={item.is_reconciled ? "Reconciled payments cannot be voided" : undefined}
                    onClick={() => setVoiding(item)}
                  >
                    Void
                  </Button>
                ) : null}
              </div>
              <BooksHistory documentType="payment" documentId={item.id} />
            </Stack>
          );
        }}
      />

      {recording ? (
        <RecordPaymentModal
          onClose={() => setRecording(false)}
          onRecorded={(payment) => {
            setRecording(false);
            changed(`Payment ${payment.payment_number} recorded against ${payment.document_number ?? "the document"}.`);
          }}
        />
      ) : null}
      {voiding ? (
        <VoidPaymentModal
          payment={voiding}
          onClose={() => setVoiding(null)}
          onVoided={(payment) => {
            setVoiding(null);
            changed(`Payment ${payment.payment_number} voided; ${payment.document_number ?? "the document"} is owing again.`);
          }}
        />
      ) : null}
    </Stack>
  );
}

function RecordPaymentModal({
  onClose,
  onRecorded,
}: {
  onClose: () => void;
  onRecorded: (payment: Payment) => void;
}) {
  const [direction, setDirection] = useState<PaymentDirection>("in");
  const [documents, setDocuments] = useState<PaymentOpenDocument[] | null>(null);
  const [documentId, setDocumentId] = useState("");
  const [amount, setAmount] = useState("");
  const [fx, setFx] = useState("");
  const [paidOn, setPaidOn] = useState(localIsoDate());
  const [method, setMethod] = useState<PaymentMethod>("eft");
  const [reference, setReference] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listOpenPaymentDocuments(direction)
      .then((items) => {
        if (!cancelled) setDocuments(items);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load open documents.");
      });
    return () => {
      cancelled = true;
    };
  }, [direction]);

  const selected = documents?.find((item) => item.document_id === documentId);
  const foreign = !!selected && selected.currency !== "ZAR";
  const noun = direction === "in" ? "invoice" : "bill";

  function changeDirection(next: PaymentDirection) {
    setDirection(next);
    setDocuments(null);
    pick("");
  }

  function pick(id: string) {
    const item = documents?.find((entry) => entry.document_id === id);
    setDocumentId(id);
    setAmount(item ? item.outstanding_foreign : "");
    setFx(item ? item.fx_to_zar : "");
  }

  async function submit() {
    if (!selected) return;
    const invalid = partialPaymentError({
      amount,
      balance: selected.outstanding_foreign,
      documentNumber: selected.number,
      currency: selected.currency,
    });
    if (invalid) {
      setError(invalid);
      return;
    }
    if (foreign && !(Number(fx) > 0)) {
      setError("Enter the rate your bank used.");
      return;
    }
    setSaving(true);
    setError(null);
    const methodFields = { tender: method, reference: reference.trim() || undefined };
    try {
      const payment = await createPayment(
        direction === "in"
          ? {
              direction: "in",
              invoice_id: selected.document_id,
              amount: amount.trim(),
              currency: "ZAR",
              paid_on: paidOn,
              ...methodFields,
            }
          : {
              direction: "out",
              bill_id: selected.document_id,
              amount: amount.trim(),
              currency: selected.currency,
              fx_to_zar: foreign ? fx.trim() : undefined,
              paid_on: paidOn,
              ...methodFields,
            },
      );
      onRecorded(payment);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to record payment.");
      setSaving(false);
    }
  }

  return (
    <Modal
      open
      modalHeading="Record payment"
      primaryButtonText={saving ? "Recording…" : "Record payment"}
      secondaryButtonText="Cancel"
      primaryButtonDisabled={saving || !selected || !amount.trim() || !paidOn}
      onRequestClose={() => {
        if (!saving) onClose();
      }}
      onRequestSubmit={() => void submit()}
    >
      <Stack gap={5}>
        {error ? <InlineNotification kind="error" title="Could not record" subtitle={error} hideCloseButton lowContrast /> : null}
        <RadioButtonGroup
          legendText="Direction"
          name="payment-direction"
          valueSelected={direction}
          onChange={(value) => changeDirection(value === "out" ? "out" : "in")}
          orientation="horizontal"
        >
          <RadioButton id="payment-direction-in" value="in" labelText="Received from a customer" />
          <RadioButton id="payment-direction-out" value="out" labelText="Paid to a supplier" />
        </RadioButtonGroup>
        <Select
          id="payment-document"
          labelText={direction === "in" ? "Invoice" : "Bill"}
          value={documentId}
          disabled={documents === null}
          helperText={documents?.length ? `Only ${noun}s with a balance owing are listed.` : undefined}
          invalid={documents !== null && documents.length === 0}
          invalidText={`There are no ${noun}s with a balance owing.`}
          onChange={(event) => pick(event.target.value)}
        >
          <SelectItem value="" text={documents === null ? "Loading…" : direction === "in" ? "Choose an invoice" : "Choose a bill"} />
          {(documents ?? []).map((item) => (
            <SelectItem
              key={item.document_id}
              value={item.document_id}
              text={`${item.number} · ${item.contact_name} · ${item.currency} ${item.outstanding_foreign} owing`}
            />
          ))}
        </Select>
        <TextInput
          id="payment-amount"
          labelText={`Amount (${selected?.currency ?? "ZAR"})`}
          helperText={selected ? `Up to ${selected.currency} ${selected.outstanding_foreign} still owing.` : undefined}
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
        />
        {foreign ? (
          <TextInput
            id="payment-fx"
            labelText={`FX rate, ${selected.currency} to ZAR`}
            helperText="The rate your bank used; it may differ from the bill's rate."
            value={fx}
            onChange={(event) => setFx(event.target.value)}
          />
        ) : null}
        <TextInput
          id="payment-date"
          labelText="Paid on"
          type="date"
          value={paidOn}
          onChange={(event) => setPaidOn(event.target.value)}
        />
        <PaymentMethodFields
          idPrefix="payment"
          method={method}
          reference={reference}
          onMethodChange={setMethod}
          onReferenceChange={setReference}
        />
      </Stack>
    </Modal>
  );
}

function VoidPaymentModal({
  payment,
  onClose,
  onVoided,
}: {
  payment: Payment;
  onClose: () => void;
  onVoided: (payment: Payment) => void;
}) {
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setSaving(true);
    setError(null);
    try {
      onVoided(await voidPayment(payment.id, reason.trim()));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to void payment.");
      setSaving(false);
    }
  }

  return (
    <Modal
      open
      danger
      size="sm"
      modalLabel={payment.payment_number}
      modalHeading="Void this payment?"
      primaryButtonText={saving ? "Voiding…" : "Void payment"}
      secondaryButtonText="Cancel"
      primaryButtonDisabled={saving || !reason.trim()}
      onRequestClose={() => {
        if (!saving) onClose();
      }}
      onRequestSubmit={() => void submit()}
    >
      <Stack gap={5}>
        {error ? <InlineNotification kind="error" title="Could not void" subtitle={error} hideCloseButton lowContrast /> : null}
        <p>
          Voiding keeps the payment on record, reverses its ledger entry and reopens {payment.currency}{" "}
          {payment.amount} on {payment.document_number ?? "its document"}. You can&apos;t undo a void.
        </p>
        <TextArea
          id="void-reason"
          labelText="Reason"
          helperText="Required. For example: EFT bounced, captured twice."
          rows={2}
          maxLength={500}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
        />
      </Stack>
    </Modal>
  );
}

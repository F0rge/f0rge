"use client";

import { ErrorNotice } from "@/components/error-notice";
import { LoadingField, LoadingRegion, LoadingTableRows } from "@/components/page-loading";
import {
  Button,
  FileUploaderDropContainer,
  InlineNotification,
  Modal,
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
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { BillPaymentModal } from "@/components/bill-payment-modal";
import { BooksHistory } from "@/components/books-history";
import { paymentMethodLabel } from "@/components/payment-method-fields";
import {
  billAction,
  canMutateBooks,
  deleteBillAttachment,
  downloadBillAttachment,
  formatFxGainLoss,
  formatZarAmount,
  getBill,
  listPayments,
  updateBill,
  uploadBillAttachment,
  type Bill,
  type BillAttachment,
  type Payment,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatSettlementAmount } from "@/lib/source-history";
import { BILL_STATUS } from "@/lib/payment-status";
import { localIsoDate } from "@/lib/dates";

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

function dueNote(bill: Bill): string | null {
  if (!bill.due_date || !["unpaid", "partially_paid", "overdue"].includes(bill.status)) return null;
  const days = Math.round(
    (Date.parse(`${bill.due_date}T00:00:00Z`) - Date.parse(`${localIsoDate()}T00:00:00Z`)) /
      86_400_000,
  );
  if (days < 0) return `Overdue by ${plural(-days, "day")}`;
  return days === 0 ? "Due today" : `Due in ${plural(days, "day")}`;
}

export default function BillDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const canMutate = canMutateBooks(user);
  const [bill, setBill] = useState<Bill | null>(null);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [paying, setPaying] = useState(false);
  const [removing, setRemoving] = useState<BillAttachment | null>(null);
  const [dueDate, setDueDate] = useState("");
  const [notes, setNotes] = useState("");

  const show = useCallback((data: Bill) => {
    setBill(data);
    setDueDate(data.due_date ?? "");
    setNotes(data.notes ?? "");
  }, []);

  const loadBill = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getBill(params.id);
      setPayments(data.is_archive ? [] : (await listPayments({ bill_id: data.id, limit: 100 })).items);
      show(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load bill.");
    } finally {
      setLoading(false);
    }
  }, [params.id, show]);

  useEffect(() => {
    if (user && params.id) {
      void loadBill();
    }
  }, [user, params.id, loadBill]);

  async function run(action: () => Promise<Bill>, message: string, failure: string) {
    setBusy(true);
    setError(null);
    try {
      show(await action());
      setSuccess(message);
    } catch (err) {
      setError(err instanceof Error ? err.message : failure);
    } finally {
      setBusy(false);
    }
  }

  async function upload(files: File[]) {
    if (!bill) return;
    for (const file of files) {
      await run(() => uploadBillAttachment(bill.id, file), `${file.name} attached.`, `Failed to upload ${file.name}.`);
    }
  }

  async function download(attachment: BillAttachment) {
    if (!bill) return;
    setError(null);
    try {
      await downloadBillAttachment(bill.id, attachment);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download attachment.");
    }
  }

  if (loading) {
    return (
      <Stack gap={6}>
        <div style={{ alignSelf: "flex-start" }}>
          <Button kind="ghost" size="sm" onClick={() => router.push("/bills")}>← Back to bills</Button>
        </div>
        <LoadingRegion label="Loading bill…">
          <Stack gap={6}>
            <div aria-hidden="true">
              <SkeletonText heading width="14rem" />
              <SkeletonText width="min(24rem, 85%)" />
              <SkeletonText width="5rem" />
            </div>
            <Stack gap={4} orientation="horizontal" aria-hidden="true">
              <LoadingField width="10rem" height="3rem" />
              {canMutate && <LoadingField width="10rem" height="3rem" />}
            </Stack>
            <div className="firstout-bill-summary">
              {["Total", "FX to ZAR", "Total ZAR", "Paid", "Balance owing", "Issue date", "Due date"].map((label) => (
                <Stack key={label} gap={2} orientation="horizontal">
                  <span className="cds--type-body-01">{label}:</span>
                  <SkeletonText width="5rem" />
                </Stack>
              ))}
            </div>
            <TableContainer title="Payments" description="Money paid against this bill">
              <LoadingTableRows columns={["Number", "Paid on", "Amount", "ZAR"]} rows={2} />
            </TableContainer>
            <TableContainer title="Lines" description="Bill line items">
              <LoadingTableRows columns={["Description", "Qty", "Unit", "Amount"]} />
            </TableContainer>
          </Stack>
        </LoadingRegion>
      </Stack>
    );
  }

  if (!bill) {
    return (
      <InlineNotification
        kind="error"
        title="Not found"
        subtitle={error ?? "Bill could not be loaded."}
        hideCloseButton
        lowContrast
      />
    );
  }

  const imported = bill.is_archive;
  const editable = canMutate && !imported && !bill.is_archived;
  const approved = bill.approval_status === "approved";
  const payable = editable && approved && Number(bill.balance_foreign) > 0;
  const status = BILL_STATUS[bill.status];
  const due = dueNote(bill);
  const detailsChanged = dueDate !== (bill.due_date ?? "") || notes.trim() !== (bill.notes ?? "");

  return (
    <Stack gap={6}>
      <div>
        <Button kind="ghost" size="sm" onClick={() => router.push("/bills")}>
          ← Back to bills
        </Button>
        <h1 className="cds--type-productive-heading-04" style={{ marginTop: "0.5rem" }}>
          {bill.bill_number}
        </h1>
        <p className="cds--type-body-01">
          {bill.supplier_name}
          {bill.supplier_ref ? ` · Ref ${bill.supplier_ref}` : ""}
        </p>
        <Tag type={status.tag} size="sm">{status.label}</Tag>
        {bill.is_archived ? <Tag type="gray" size="sm">Archived</Tag> : null}
      </div>

      {canMutate && !imported ? (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.75rem" }}>
          {editable && !approved ? (
            <Button
              disabled={busy}
              onClick={() =>
                void run(() => billAction(bill.id, "approve"), "Bill approved and posted. It's ready to pay.", "Failed to approve bill.")
              }
            >
              Approve
            </Button>
          ) : null}
          {editable && bill.approval_status === "draft" ? (
            <Button
              kind="secondary"
              disabled={busy}
              onClick={() =>
                void run(() => billAction(bill.id, "submit"), "Bill submitted for approval.", "Failed to submit bill.")
              }
            >
              Submit for approval
            </Button>
          ) : null}
          {payable ? (
            <Button disabled={busy} onClick={() => setPaying(true)}>
              Record payment
            </Button>
          ) : null}
          <Button kind="tertiary" href={`/bills/new?from=${bill.id}`}>
            Duplicate
          </Button>
          <Button
            kind="ghost"
            disabled={busy}
            onClick={() =>
              void run(
                () => billAction(bill.id, bill.is_archived ? "restore" : "archive"),
                bill.is_archived ? "Bill restored." : "Bill archived. Find it under Archived.",
                "Failed to update bill.",
              )
            }
          >
            {bill.is_archived ? "Restore" : "Archive"}
          </Button>
        </div>
      ) : null}

      {imported ? (
        <InlineNotification
          kind="info"
          title="Imported history; payments and opening balances were not imported"
          subtitle="This bill is read-only. Source totals are preserved; payment status and balances are not imported."
          hideCloseButton
          lowContrast
        />
      ) : null}
      {bill.is_archived ? (
        <InlineNotification
          kind="info"
          title="This bill is archived."
          subtitle="It's hidden from the active list and the totals. Restore it to change or pay it."
          hideCloseButton
          lowContrast
        />
      ) : null}
      {!imported && !approved && !bill.is_archived ? (
        <InlineNotification
          kind="info"
          title={bill.approval_status === "draft" ? "Draft." : "Waiting for approval."}
          subtitle="Approve this bill before you record a payment against it. Approving posts it to the ledger."
          hideCloseButton
          lowContrast
        />
      ) : null}
      {success ? (
        <InlineNotification kind="success" title="Done" subtitle={success} onCloseButtonClick={() => setSuccess(null)} lowContrast />
      ) : null}
      <ErrorNotice error={error} onClose={() => setError(null)} />

      <div className="firstout-bill-summary">
        <p className="cds--type-body-01">
          Total: {bill.currency} {bill.amount_foreign}
        </p>
        <p className="cds--type-body-01">FX to ZAR: {bill.fx_rate_known ? bill.fx_to_zar : "Not provided in source"}</p>
        <p className="cds--type-body-01">Total ZAR: {bill.fx_rate_known ? formatZarAmount(bill.amount_zar) : "Not provided in source"}</p>
        <p className="cds--type-body-01">Paid ZAR: {formatSettlementAmount(bill.amount_paid_zar, imported)}</p>
        <p className="cds--type-body-01">
          Balance owing:{" "}
          {formatSettlementAmount(bill.balance_foreign, imported, (value) => `${bill.currency} ${value}`)}
          {bill.currency !== "ZAR" && !imported ? ` · ${formatZarAmount(bill.balance_zar)}` : ""}
        </p>
        <p className="cds--type-body-01">Issue date: {bill.issue_date}</p>
        <p className="cds--type-body-01">
          Due date: {bill.due_date ?? "—"}
          {due ? ` (${due})` : ""}
        </p>
      </div>

      {editable ? (
        <Stack gap={4}>
          <p className="cds--type-productive-heading-02">Due date and notes</p>
          <TextInput
            id="bill-due-date"
            labelText="Due date"
            type="date"
            value={dueDate}
            invalid={!!dueDate && dueDate < bill.issue_date}
            invalidText="The due date can't be before the issue date."
            onChange={(event) => setDueDate(event.target.value)}
          />
          <TextArea
            id="bill-notes"
            labelText="Notes"
            helperText="Staff only."
            rows={3}
            maxLength={4000}
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
          />
          <div>
            <Button
              kind="secondary"
              size="sm"
              disabled={busy || !detailsChanged || !dueDate || dueDate < bill.issue_date}
              onClick={() =>
                void run(
                  () => updateBill(bill.id, { due_date: dueDate, notes: notes.trim() || null }),
                  "Bill details saved.",
                  "Failed to save bill details.",
                )
              }
            >
              Save details
            </Button>
          </div>
        </Stack>
      ) : bill.notes ? (
        <p className="cds--type-body-01">Notes: {bill.notes}</p>
      ) : null}

      <TableContainer title="Attachments" description="Supplier invoices, delivery notes and other files">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeader>File</TableHeader>
              <TableHeader>Added</TableHeader>
              <TableHeader />
            </TableRow>
          </TableHead>
          <TableBody>
            {bill.attachments.length === 0 ? (
              <TableRow>
                <TableCell colSpan={3}>No files yet.</TableCell>
              </TableRow>
            ) : (
              bill.attachments.map((attachment) => (
                <TableRow key={attachment.id}>
                  <TableCell>{attachment.filename}</TableCell>
                  <TableCell>{attachment.uploaded_at.slice(0, 10)}</TableCell>
                  <TableCell>
                    <Button kind="ghost" size="sm" onClick={() => void download(attachment)}>
                      Download
                    </Button>
                    {editable && !attachment.read_only ? (
                      <Button
                        kind="danger--ghost"
                        size="sm"
                        disabled={busy}
                        onClick={() => setRemoving(attachment)}
                      >
                        Remove
                      </Button>
                    ) : null}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>
      {editable ? (
        <FileUploaderDropContainer
          accept={["application/pdf", ".pdf", "image/png", ".png", "image/jpeg", ".jpg", ".jpeg"]}
          labelText={busy ? "Uploading…" : "Add files: drag a PDF or image here, or click to choose"}
          multiple
          disabled={busy}
          onAddFiles={(_, { addedFiles }) => void upload(addedFiles.filter((file) => !file.invalidFileType))}
        />
      ) : null}

      {imported ? (
        <p className="cds--type-body-01">Payments: Not imported</p>
      ) : (
        <TableContainer title="Payments" description="Money paid against this bill">
          <Table>
            <TableHead>
              <TableRow>
                <TableHeader>Number</TableHeader>
                <TableHeader>Paid on</TableHeader>
                <TableHeader>Amount</TableHeader>
                <TableHeader>ZAR</TableHeader>
                <TableHeader>FX gain/loss</TableHeader>
                <TableHeader>Method</TableHeader>
                <TableHeader>Reference</TableHeader>
                <TableHeader>Status</TableHeader>
              </TableRow>
            </TableHead>
            <TableBody>
              {payments.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8}>No payments recorded yet.</TableCell>
                </TableRow>
              ) : (
                payments.map((payment) => (
                  <TableRow key={payment.id}>
                    <TableCell>{payment.payment_number}</TableCell>
                    <TableCell>{payment.paid_on}</TableCell>
                    <TableCell>
                      {payment.currency} {payment.amount}
                    </TableCell>
                    <TableCell>{formatZarAmount(payment.amount_zar)}</TableCell>
                    <TableCell>{formatFxGainLoss(payment.fx_gain_loss_zar)}</TableCell>
                    <TableCell>{paymentMethodLabel(payment.tender)}</TableCell>
                    <TableCell>{payment.reference ?? "—"}</TableCell>
                    <TableCell>{payment.is_voided ? "Voided" : payment.is_reconciled ? "Reconciled" : "Unreconciled"}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <TableContainer title="Lines" description="Bill line items">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeader>Description</TableHeader>
              <TableHeader>Qty</TableHeader>
              {!imported ? <TableHeader>Unit</TableHeader> : null}
              <TableHeader>Amount</TableHeader>
            </TableRow>
          </TableHead>
          <TableBody>
            {bill.lines.map((line) => (
              <TableRow key={line.id}>
                <TableCell>{line.description}</TableCell>
                <TableCell>{line.qty}</TableCell>
                {!imported ? (
                  <TableCell>
                    {bill.currency} {line.unit_amount}
                  </TableCell>
                ) : null}
                <TableCell>
                  {bill.currency} {line.amount_foreign}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <BooksHistory key={bill.updated_at} documentType="bill" documentId={bill.id} />

      {paying ? (
        <BillPaymentModal
          bill={bill}
          onClose={() => setPaying(false)}
          onRecorded={(payment) => {
            setPaying(false);
            setSuccess(`Payment ${payment.payment_number} recorded. FX: ${formatFxGainLoss(payment.fx_gain_loss_zar)}.`);
            void loadBill();
          }}
        />
      ) : null}

      {removing ? (
        <Modal
          open
          danger
          size="sm"
          modalLabel={bill.bill_number}
          modalHeading={`Remove ${removing.filename}?`}
          primaryButtonText="Remove"
          secondaryButtonText="Cancel"
          primaryButtonDisabled={busy}
          onRequestClose={() => {
            if (!busy) setRemoving(null);
          }}
          onRequestSubmit={() => {
            const attachment = removing;
            setRemoving(null);
            void run(
              () => deleteBillAttachment(bill.id, attachment.id),
              `${attachment.filename} removed.`,
              "Failed to remove attachment.",
            );
          }}
        >
          <p className="cds--type-body-01">The file is deleted from this bill. This cannot be undone.</p>
        </Modal>
      ) : null}
    </Stack>
  );
}

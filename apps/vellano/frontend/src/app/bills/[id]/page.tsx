"use client";

import {
  Button,
  FileUploaderDropContainer,
  FileUploaderItem,
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
  TextInput,
} from "@carbon/react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { BooksHistory } from "@/components/books-history";
import {
  canMutateBooks,
  createPayment,
  downloadBillAttachment,
  formatFxGainLoss,
  formatZarAmount,
  getBill,
  uploadBillAttachment,
  type Bill,
  type Payment,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function hasPositiveBalance(balance: string): boolean {
  return Number(balance) > 0;
}

export default function BillDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const canMutate = canMutateBooks(user);
  const [bill, setBill] = useState<Bill | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [paymentOpen, setPaymentOpen] = useState(false);
  const [paymentAmount, setPaymentAmount] = useState("");
  const [paymentCurrency, setPaymentCurrency] = useState("USD");
  const [paymentFx, setPaymentFx] = useState("");
  const [paymentDate, setPaymentDate] = useState(todayIso());
  const [lastPayment, setLastPayment] = useState<Payment | null>(null);

  const loadBill = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getBill(params.id);
      setBill(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load bill.");
    } finally {
      setLoading(false);
    }
  }, [params.id]);

  useEffect(() => {
    if (user && params.id) {
      void loadBill();
    }
  }, [user, params.id, loadBill]);

  async function handleDownload() {
    if (!bill) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await downloadBillAttachment(bill.id, bill.bill_number);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download attachment.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleUpload() {
    if (!bill || !uploadFile) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const updated = await uploadBillAttachment(bill.id, uploadFile);
      setBill(updated);
      setUploadFile(null);
      setSuccess("Attachment uploaded.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload attachment.");
    } finally {
      setActionLoading(false);
    }
  }

  function openPaymentModal() {
    if (!bill) {
      return;
    }
    setPaymentAmount(bill.amount_foreign);
    setPaymentCurrency(bill.currency);
    setPaymentFx(bill.fx_to_zar);
    setPaymentDate(todayIso());
    setPaymentOpen(true);
  }

  async function handleRecordPayment() {
    if (!bill) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const payment = await createPayment({
        direction: "out",
        bill_id: bill.id,
        amount: paymentAmount.trim(),
        currency: paymentCurrency.trim(),
        fx_to_zar: paymentCurrency === "ZAR" ? undefined : paymentFx.trim(),
        paid_on: paymentDate,
      });
      setLastPayment(payment);
      setPaymentOpen(false);
      setSuccess(
        `Payment ${payment.payment_number} recorded. FX: ${formatFxGainLoss(payment.fx_gain_loss_zar)}.`,
      );
      await loadBill();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to record payment.");
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) {
    return <p className="cds--type-body-01">Loading bill…</p>;
  }

  if (!bill) {
    return (
      <InlineNotification
        kind="error"
        title="Not found"
        subtitle="Bill could not be loaded."
        hideCloseButton
        lowContrast
      />
    );
  }

  const showPayment = canMutate && hasPositiveBalance(bill.balance_zar);

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
          {bill.supplier_name} · Ref {bill.supplier_ref} · {bill.issue_date}
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
        {bill.pdf_storage_key ? (
          <Button kind="secondary" disabled={actionLoading} onClick={() => void handleDownload()}>
            Download attachment
          </Button>
        ) : null}
        {showPayment ? (
          <Button disabled={actionLoading} onClick={openPaymentModal}>
            Record payment out
          </Button>
        ) : null}
      </Stack>

      <div className="vellano-bill-summary">
        <p className="cds--type-body-01">
          Amount: {bill.currency} {bill.amount_foreign}
        </p>
        <p className="cds--type-body-01">FX to ZAR: {bill.fx_to_zar}</p>
        <p className="cds--type-body-01">Amount ZAR: {formatZarAmount(bill.amount_zar)}</p>
        <p className="cds--type-body-01">Paid ZAR: {formatZarAmount(bill.amount_paid_zar)}</p>
        <p className="cds--type-body-01">Balance ZAR: {formatZarAmount(bill.balance_zar)}</p>
      </div>

      {lastPayment ? (
        <InlineNotification
          kind="info"
          title="FX gain/loss"
          subtitle={formatFxGainLoss(lastPayment.fx_gain_loss_zar)}
          hideCloseButton
          lowContrast
        />
      ) : null}

      <TableContainer title="Lines" description="Bill line items">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeader>Description</TableHeader>
              <TableHeader>Qty</TableHeader>
              <TableHeader>Unit</TableHeader>
              <TableHeader>Amount</TableHeader>
            </TableRow>
          </TableHead>
          <TableBody>
            {bill.lines.map((line) => (
              <TableRow key={line.id}>
                <TableCell>{line.description}</TableCell>
                <TableCell>{line.qty}</TableCell>
                <TableCell>
                  {bill.currency} {line.unit_amount}
                </TableCell>
                <TableCell>
                  {bill.currency} {line.amount_foreign}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>

      <BooksHistory documentType="bill" documentId={bill.id} />

      {canMutate ? (
        <Stack gap={4}>
          <p className="cds--type-productive-heading-02">Attachment</p>
          {bill.pdf_storage_key ? (
            <p className="cds--type-body-01">PDF on file. Upload a new file to replace it.</p>
          ) : (
            <p className="cds--type-body-01">No PDF attached yet.</p>
          )}
          <FileUploaderDropContainer
            accept={["application/pdf", ".pdf"]}
            labelText="Upload PDF"
            multiple={false}
            onAddFiles={(_, { addedFiles }) => {
              const file = addedFiles[0];
              if (file && !file.invalidFileType) {
                setUploadFile(file);
              }
            }}
          />
          {uploadFile ? (
            <FileUploaderItem
              name={uploadFile.name}
              status="complete"
              onDelete={() => setUploadFile(null)}
            />
          ) : null}
          <Button
            kind="secondary"
            disabled={actionLoading || !uploadFile}
            onClick={() => void handleUpload()}
          >
            {actionLoading ? "Uploading…" : "Upload attachment"}
          </Button>
        </Stack>
      ) : null}

      <Modal
        open={paymentOpen}
        modalHeading="Record payment out"
        primaryButtonText={actionLoading ? "Recording…" : "Record payment"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={
          actionLoading ||
          !paymentAmount.trim() ||
          !paymentCurrency.trim() ||
          !paymentDate ||
          (paymentCurrency !== "ZAR" && !paymentFx.trim())
        }
        onRequestClose={() => setPaymentOpen(false)}
        onRequestSubmit={() => void handleRecordPayment()}
      >
        <Stack gap={5}>
          <TextInput
            id="bill-payment-amount"
            labelText="Amount"
            helperText="Must equal the full bill foreign amount."
            value={paymentAmount}
            onChange={(event) => setPaymentAmount(event.target.value)}
            required
          />
          <TextInput
            id="bill-payment-currency"
            labelText="Currency"
            value={paymentCurrency}
            onChange={(event) => setPaymentCurrency(event.target.value)}
            required
          />
          {paymentCurrency !== "ZAR" ? (
            <TextInput
              id="bill-payment-fx"
              labelText="FX to ZAR"
              helperText="Enter the rate used for this payment (may differ from bill rate)."
              value={paymentFx}
              onChange={(event) => setPaymentFx(event.target.value)}
              required
            />
          ) : null}
          <TextInput
            id="bill-payment-date"
            labelText="Paid on"
            type="date"
            value={paymentDate}
            onChange={(event) => setPaymentDate(event.target.value)}
            required
          />
        </Stack>
      </Modal>
    </Stack>
  );
}

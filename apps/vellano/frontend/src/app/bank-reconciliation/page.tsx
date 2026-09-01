"use client";

import {
  Button,
  DataTable,
  FileUploaderDropContainer,
  FileUploaderItem,
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
  Tag,
} from "@carbon/react";
import { useCallback, useEffect, useState } from "react";

import {
  canMutateBooks,
  formatZarAmount,
  getBankImport,
  listBankImports,
  listPayments,
  matchBankLine,
  uploadBankImport,
  type BankImport,
  type BankImportSummary,
  type Payment,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const LINE_HEADERS = [
  { key: "transaction_date", header: "Date" },
  { key: "description", header: "Description" },
  { key: "reference", header: "Reference" },
  { key: "amount_zar", header: "Amount" },
  { key: "status", header: "Status" },
  { key: "actions", header: "" },
] as const;

export default function BankReconciliationPage() {
  const { user } = useAuth();
  const canMutate = canMutateBooks(user?.role);
  const [imports, setImports] = useState<BankImportSummary[]>([]);
  const [selectedImport, setSelectedImport] = useState<BankImport | null>(null);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [matchLineId, setMatchLineId] = useState<string | null>(null);
  const [matchPaymentId, setMatchPaymentId] = useState<string>("");
  const [matching, setMatching] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [importList, paymentList] = await Promise.all([listBankImports(), listPayments()]);
      setImports(importList);
      setPayments(paymentList);
      if (importList.length > 0) {
        const detail = await getBankImport(importList[0].id);
        setSelectedImport(detail);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load bank imports.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadData();
    }
  }, [user, loadData]);

  async function handleUpload() {
    if (files.length === 0) {
      return;
    }
    setUploading(true);
    setError(null);
    setSuccess(null);
    try {
      const result = await uploadBankImport(files[0]);
      setSuccess(`Imported ${result.line_count} lines from ${result.filename}`);
      setFiles([]);
      await loadData();
      setSelectedImport(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function handleSelectImport(importId: string) {
    try {
      const detail = await getBankImport(importId);
      setSelectedImport(detail);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load import.");
    }
  }

  async function handleMatch() {
    if (!selectedImport || !matchLineId || !matchPaymentId) {
      return;
    }
    setMatching(true);
    setError(null);
    try {
      await matchBankLine(selectedImport.id, matchLineId, matchPaymentId);
      setSuccess("Payment matched and reconciled.");
      setMatchLineId(null);
      setMatchPaymentId("");
      const detail = await getBankImport(selectedImport.id);
      setSelectedImport(detail);
      const paymentList = await listPayments();
      setPayments(paymentList);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Match failed.");
    } finally {
      setMatching(false);
    }
  }

  function openMatchModal(lineId: string, suggestedPaymentId: string | null) {
    setMatchLineId(lineId);
    setMatchPaymentId(suggestedPaymentId ?? "");
  }

  const unreconciledPayments = payments.filter((p) => !p.is_reconciled);

  const lineRows =
    selectedImport?.lines.map((line) => ({
      id: line.id,
      transaction_date: line.transaction_date,
      description: line.description,
      reference: line.reference ?? "—",
      amount_zar: formatZarAmount(line.amount_zar),
      status: line.matched_payment_id
        ? `Matched ${line.matched_payment_number ?? ""}`
        : line.suggested_payment_number
          ? `Suggested ${line.suggested_payment_number}`
          : "Unmatched",
      actions: line.matched_payment_id ? "" : "match",
      _suggested: line.suggested_payment_id,
    })) ?? [];

  return (
    <Stack gap={6}>
      <div>
        <h1 className="cds--type-productive-heading-04">Bank reconciliation</h1>
        <p className="cds--type-body-01">
          Import bank CSV statements and match lines to recorded payments.
        </p>
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
          title="Success"
          subtitle={success}
          onCloseButtonClick={() => setSuccess(null)}
          lowContrast
        />
      ) : null}

      {canMutate ? (
        <div>
          <p className="cds--label">Upload bank CSV</p>
          <p className="cds--helper-text">
            SA bank CSV with Date, Description, and Amount (or Debit/Credit) columns.
          </p>
          <FileUploaderDropContainer
            accept={[".csv", "text/csv"]}
            labelText="Drag and drop a CSV here or click to upload"
            multiple={false}
            disabled={uploading}
            onAddFiles={(_, { addedFiles }) => setFiles(addedFiles)}
          />
          {files.map((file) => (
            <FileUploaderItem
              key={file.name}
              name={file.name}
              status="complete"
              onDelete={() => setFiles([])}
            />
          ))}
          {files.length > 0 ? (
            <Button kind="primary" disabled={uploading} onClick={() => void handleUpload()}>
              {uploading ? "Uploading…" : "Import CSV"}
            </Button>
          ) : null}
        </div>
      ) : null}

      {loading ? (
        <p className="cds--type-body-01">Loading…</p>
      ) : imports.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No imports"
          subtitle="Upload a bank CSV to begin reconciliation."
          hideCloseButton
          lowContrast
        />
      ) : (
        <Stack gap={4}>
          <Select
            id="import-select"
            labelText="Import"
            value={selectedImport?.id ?? ""}
            onChange={(event) => void handleSelectImport(event.target.value)}
          >
            {imports.map((entry) => (
              <SelectItem
                key={entry.id}
                value={entry.id}
                text={`${entry.filename} (${entry.matched_count}/${entry.line_count} matched)`}
              />
            ))}
          </Select>

          {selectedImport ? (
            <DataTable rows={lineRows} headers={[...LINE_HEADERS]}>
              {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
                <TableContainer
                  title="Import lines"
                  description={`${selectedImport.filename} — unmatched lines remain visible until matched`}
                >
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
                        const lineData = lineRows.find((l) => l.id === row.id);
                        const isMatched = lineData?.actions !== "match";
                        return (
                          <TableRow {...getRowProps({ row })} key={row.id}>
                            {row.cells.map((cell) => (
                              <TableCell key={cell.id}>
                                {cell.info.header === "status" && isMatched ? (
                                  <Tag type="green">{cell.value}</Tag>
                                ) : cell.info.header === "status" && !isMatched ? (
                                  <Tag type="gray">{cell.value}</Tag>
                                ) : cell.info.header === "actions" && canMutate && lineData?.actions === "match" ? (
                                  <Button
                                    kind="ghost"
                                    size="sm"
                                    onClick={() => openMatchModal(row.id, lineData._suggested)}
                                  >
                                    Match
                                  </Button>
                                ) : (
                                  cell.value
                                )}
                              </TableCell>
                            ))}
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </DataTable>
          ) : null}
        </Stack>
      )}

      <Modal
        open={matchLineId !== null}
        modalHeading="Match to payment"
        primaryButtonText={matching ? "Matching…" : "Match"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={!matchPaymentId || matching}
        onRequestClose={() => {
          setMatchLineId(null);
          setMatchPaymentId("");
        }}
        onRequestSubmit={() => void handleMatch()}
      >
        <Select
          id="payment-select"
          labelText="Payment"
          value={matchPaymentId}
          onChange={(event) => setMatchPaymentId(event.target.value)}
        >
          <SelectItem value="" text="Select payment" />
          {unreconciledPayments.map((payment) => (
            <SelectItem
              key={payment.id}
              value={payment.id}
              text={`${payment.payment_number} — ${formatZarAmount(payment.amount_zar)} on ${payment.paid_on}`}
            />
          ))}
        </Select>
      </Modal>
    </Stack>
  );
}

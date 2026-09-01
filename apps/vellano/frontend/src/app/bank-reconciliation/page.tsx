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
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  applyRule,
  canMutateBooks,
  formatZarAmount,
  getBankImport,
  listAccounts,
  listBankImports,
  listJournals,
  listPayments,
  listUnmatchedCounts,
  listUnmatchedLines,
  matchBankLine,
  recodeLine,
  uploadBankImport,
  type Account,
  type BankImport,
  type BankImportLine,
  type BankImportSummary,
  type BankUnmatchedCount,
  type Journal,
  type Payment,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

import { BankRulesModal } from "./bank-rules-modal";

const LINE_HEADERS = [
  { key: "transaction_date", header: "Date" },
  { key: "description", header: "Description" },
  { key: "reference", header: "Reference" },
  { key: "amount_zar", header: "Amount" },
  { key: "status", header: "Status" },
  { key: "actions", header: "" },
] as const;

const UNMATCHED_HEADERS = [
  { key: "transaction_date", header: "Date" },
  { key: "description", header: "Description" },
  { key: "reference", header: "Reference" },
  { key: "amount_zar", header: "Amount" },
  { key: "suggestion", header: "Suggestion" },
  { key: "actions", header: "" },
] as const;

function isLineMatched(line: BankImportLine): boolean {
  return Boolean(line.matched_payment_id || line.matched_journal_id);
}

function lineStatus(line: BankImportLine, journals: Journal[]): string {
  if (line.matched_payment_id) {
    return `Matched ${line.matched_payment_number ?? ""}`.trim();
  }
  if (line.matched_journal_id) {
    const number =
      line.matched_journal_number ??
      journals.find((journal) => journal.id === line.matched_journal_id)?.journal_number;
    return number ? `Matched ${number}` : "Matched journal";
  }
  if (line.suggested_payment_number) {
    return `Suggested ${line.suggested_payment_number}`;
  }
  if (line.suggested_rule_pattern) {
    const dest = [line.suggested_account_code, line.suggested_account_name]
      .filter(Boolean)
      .join(" ");
    return dest
      ? `Suggested ${line.suggested_rule_pattern} → ${dest}`
      : `Suggested ${line.suggested_rule_pattern}`;
  }
  return "Unmatched";
}

function ruleSuggestion(line: BankImportLine): string {
  if (!line.suggested_rule_id) {
    return "—";
  }
  const dest = [line.suggested_account_code, line.suggested_account_name]
    .filter(Boolean)
    .join(" ");
  const pattern = line.suggested_rule_pattern ?? "rule";
  return dest ? `${pattern} → ${dest}` : pattern;
}

function accountLabel(account: Pick<Account, "code" | "name">): string {
  return `${account.code} ${account.name}`;
}

function LineActions({
  line,
  canMutate,
  onMatch,
  onApply,
  onRecode,
}: {
  line: BankImportLine;
  canMutate: boolean;
  onMatch: () => void;
  onApply: () => void;
  onRecode: () => void;
}) {
  if (!canMutate) {
    return null;
  }
  const unmatched = !isLineMatched(line);
  return (
    <Stack gap={2} orientation="horizontal">
      {unmatched && line.suggested_rule_id ? (
        <Button kind="tertiary" size="sm" onClick={onApply}>
          Apply rule
        </Button>
      ) : null}
      {unmatched ? (
        <Button kind="ghost" size="sm" onClick={onMatch}>
          Match
        </Button>
      ) : null}
      {line.matched_journal_id && !line.matched_payment_id ? (
        <Button kind="ghost" size="sm" onClick={onRecode}>
          Recode
        </Button>
      ) : null}
    </Stack>
  );
}

export default function BankReconciliationPage() {
  const { user } = useAuth();
  const canMutate = canMutateBooks(user?.role);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [accountId, setAccountId] = useState("");
  const [unmatchedCounts, setUnmatchedCounts] = useState<BankUnmatchedCount[]>([]);
  const [unmatchedLines, setUnmatchedLines] = useState<BankImportLine[]>([]);
  const [imports, setImports] = useState<BankImportSummary[]>([]);
  const [selectedImport, setSelectedImport] = useState<BankImport | null>(null);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [journals, setJournals] = useState<Journal[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [matchImportId, setMatchImportId] = useState<string | null>(null);
  const [matchLineId, setMatchLineId] = useState<string | null>(null);
  const [matchPaymentId, setMatchPaymentId] = useState("");
  const [matchJournalId, setMatchJournalId] = useState("");
  const [matching, setMatching] = useState(false);
  const [rulesOpen, setRulesOpen] = useState(false);
  const [applyImportId, setApplyImportId] = useState<string | null>(null);
  const [applyLine, setApplyLine] = useState<BankImportLine | null>(null);
  const [applying, setApplying] = useState(false);
  const [recodeImportId, setRecodeImportId] = useState<string | null>(null);
  const [recodeLineRow, setRecodeLineRow] = useState<BankImportLine | null>(null);
  const [recodeAccountId, setRecodeAccountId] = useState("");
  const [recoding, setRecoding] = useState(false);
  const importIdByLineRef = useRef<Record<string, string>>({});
  const selectedImportIdRef = useRef<string | null>(null);

  const bankAccounts = useMemo(
    () =>
      accounts
        .filter((account) => account.is_bank)
        .sort((left, right) => left.code.localeCompare(right.code)),
    [accounts],
  );

  const recodeAccounts = useMemo(
    () =>
      accounts
        .filter((account) => !account.is_archived && account.id !== accountId)
        .sort((left, right) => left.code.localeCompare(right.code)),
    [accounts, accountId],
  );

  const unmatchedById = useMemo(
    () => new Map(unmatchedLines.map((line) => [line.id, line])),
    [unmatchedLines],
  );

  const importLineById = useMemo(
    () => new Map((selectedImport?.lines ?? []).map((line) => [line.id, line])),
    [selectedImport],
  );

  const rememberImportLines = useCallback((detail: BankImport) => {
    for (const line of detail.lines) {
      importIdByLineRef.current[line.id] = detail.id;
    }
  }, []);

  const loadLists = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [importList, paymentList, accountList, journalList, counts] = await Promise.all([
        listBankImports(),
        listPayments(),
        listAccounts(),
        listJournals(),
        listUnmatchedCounts(),
      ]);
      const banks = accountList
        .filter((account) => account.is_bank)
        .sort((left, right) => left.code.localeCompare(right.code));
      setAccounts(accountList);
      setImports(importList);
      setPayments(paymentList);
      setJournals(journalList);
      setUnmatchedCounts(counts);
      setAccountId((current) => {
        if (current && banks.some((account) => account.id === current)) {
          return current;
        }
        return banks[0]?.id ?? "";
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load bank imports.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadLists();
    }
  }, [user, loadLists]);

  useEffect(() => {
    selectedImportIdRef.current = selectedImport?.id ?? null;
  }, [selectedImport]);

  useEffect(() => {
    if (!user || !accountId) {
      setUnmatchedLines([]);
      setSelectedImport(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    void (async () => {
      try {
        const unmatched = await listUnmatchedLines(accountId);
        if (cancelled) {
          return;
        }
        setUnmatchedLines(unmatched);
        const filtered = imports.filter((entry) => entry.account_id === accountId);
        if (filtered.length === 0) {
          setSelectedImport(null);
          return;
        }
        const currentId = selectedImportIdRef.current;
        const keepId =
          currentId && filtered.some((entry) => entry.id === currentId)
            ? currentId
            : filtered[0].id;
        const detail = await getBankImport(keepId);
        if (cancelled) {
          return;
        }
        rememberImportLines(detail);
        setSelectedImport(detail);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load unmatched lines.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user, accountId, imports, rememberImportLines]);

  const filteredImports = useMemo(
    () => imports.filter((entry) => entry.account_id === accountId),
    [imports, accountId],
  );

  const postedJournals = useMemo(
    () => journals.filter((journal) => journal.status === "posted"),
    [journals],
  );

  const unreconciledPayments = payments.filter((payment) => !payment.is_reconciled);

  const refreshAfterMutation = useCallback(
    async (importId: string | null) => {
      const [paymentList, unmatched, counts, importList, journalList] = await Promise.all([
        listPayments(),
        accountId ? listUnmatchedLines(accountId) : Promise.resolve([]),
        listUnmatchedCounts(),
        listBankImports(),
        listJournals(),
      ]);
      setPayments(paymentList);
      setUnmatchedLines(unmatched);
      setUnmatchedCounts(counts);
      setImports(importList);
      setJournals(journalList);
      if (importId) {
        const detail = await getBankImport(importId);
        rememberImportLines(detail);
        setSelectedImport(detail);
      }
    },
    [accountId, rememberImportLines],
  );

  async function resolveImportId(lineId: string): Promise<string | null> {
    const cached = importIdByLineRef.current[lineId];
    if (cached) {
      return cached;
    }
    if (selectedImport?.lines.some((line) => line.id === lineId)) {
      return selectedImport.id;
    }
    for (const entry of filteredImports) {
      const detail = await getBankImport(entry.id);
      rememberImportLines(detail);
      if (detail.lines.some((line) => line.id === lineId)) {
        setSelectedImport(detail);
        return detail.id;
      }
    }
    return null;
  }

  async function handleUpload() {
    if (files.length === 0 || !accountId) {
      return;
    }
    setUploading(true);
    setError(null);
    setSuccess(null);
    try {
      const result = await uploadBankImport(files[0], accountId);
      rememberImportLines(result);
      setSuccess(
        `Imported ${result.line_count} lines from ${result.filename} into ${result.account_code} ${result.account_name}`,
      );
      setFiles([]);
      setSelectedImport(result);
      await loadLists();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function handleSelectImport(importId: string) {
    try {
      const detail = await getBankImport(importId);
      rememberImportLines(detail);
      setSelectedImport(detail);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load import.");
    }
  }

  async function handleMatch() {
    const hasPayment = Boolean(matchPaymentId);
    const hasJournal = Boolean(matchJournalId);
    if (!matchImportId || !matchLineId || hasPayment === hasJournal) {
      return;
    }
    setMatching(true);
    setError(null);
    try {
      await matchBankLine(
        matchImportId,
        matchLineId,
        hasPayment ? { payment_id: matchPaymentId } : { journal_id: matchJournalId },
      );
      setSuccess(hasPayment ? "Payment matched and reconciled." : "Journal matched.");
      setMatchImportId(null);
      setMatchLineId(null);
      setMatchPaymentId("");
      setMatchJournalId("");
      await refreshAfterMutation(matchImportId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Match failed.");
    } finally {
      setMatching(false);
    }
  }

  async function openMatchModal(lineId: string, suggestedPaymentId: string | null) {
    const importId = await resolveImportId(lineId);
    if (!importId) {
      setError("Could not find the import for this line.");
      return;
    }
    setMatchImportId(importId);
    setMatchLineId(lineId);
    setMatchPaymentId(suggestedPaymentId ?? "");
    setMatchJournalId("");
  }

  async function openApplyModal(line: BankImportLine) {
    if (!line.suggested_rule_id) {
      return;
    }
    const importId = await resolveImportId(line.id);
    if (!importId) {
      setError("Could not find the import for this line.");
      return;
    }
    setApplyImportId(importId);
    setApplyLine(line);
  }

  async function handleApplyRule() {
    if (!applyImportId || !applyLine?.suggested_rule_id) {
      return;
    }
    setApplying(true);
    setError(null);
    try {
      await applyRule(applyImportId, applyLine.id, applyLine.suggested_rule_id);
      setSuccess(
        `Applied ${applyLine.suggested_rule_pattern ?? "rule"} and posted a journal.`,
      );
      const importId = applyImportId;
      setApplyImportId(null);
      setApplyLine(null);
      await refreshAfterMutation(importId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Apply rule failed.");
    } finally {
      setApplying(false);
    }
  }

  async function openRecodeModal(line: BankImportLine) {
    const importId = await resolveImportId(line.id);
    if (!importId) {
      setError("Could not find the import for this line.");
      return;
    }
    setRecodeImportId(importId);
    setRecodeLineRow(line);
    setRecodeAccountId("");
  }

  async function handleRecode() {
    if (!recodeImportId || !recodeLineRow || !recodeAccountId) {
      return;
    }
    setRecoding(true);
    setError(null);
    try {
      await recodeLine(recodeImportId, recodeLineRow.id, recodeAccountId);
      setSuccess("Line recoded.");
      const importId = recodeImportId;
      setRecodeImportId(null);
      setRecodeLineRow(null);
      setRecodeAccountId("");
      await refreshAfterMutation(importId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Recode failed.");
    } finally {
      setRecoding(false);
    }
  }

  const canMatch = Boolean(matchPaymentId) !== Boolean(matchJournalId);

  const unmatchedRows = unmatchedLines.map((line) => ({
    id: line.id,
    transaction_date: line.transaction_date,
    description: line.description,
    reference: line.reference ?? "—",
    amount_zar: formatZarAmount(line.amount_zar),
    suggestion: ruleSuggestion(line),
    actions: "actions",
  }));

  const lineRows =
    selectedImport?.lines.map((line) => ({
      id: line.id,
      transaction_date: line.transaction_date,
      description: line.description,
      reference: line.reference ?? "—",
      amount_zar: formatZarAmount(line.amount_zar),
      status: lineStatus(line, journals),
      actions: "actions",
    })) ?? [];

  return (
    <Stack gap={6}>
      <div>
        <h1 className="cds--type-productive-heading-04">Bank reconciliation</h1>
        <p className="cds--type-body-01">
          Import a bank CSV against a recon account and match lines to a payment or a posted journal.
          Suggested bank rules apply with one confirm.
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

      <Stack gap={3}>
        <Select
          id="bank-account-select"
          labelText="Recon account"
          helperText="Required for a new import. Unmatched queue and imports follow this account."
          value={accountId}
          onChange={(event) => setAccountId(event.target.value)}
        >
          {bankAccounts.length === 0 ? <SelectItem value="" text="No bank accounts" /> : null}
          {bankAccounts.map((account) => (
            <SelectItem key={account.id} value={account.id} text={accountLabel(account)} />
          ))}
        </Select>
        <Button
          kind="ghost"
          size="sm"
          disabled={!accountId}
          onClick={() => setRulesOpen(true)}
        >
          Rules
        </Button>
      </Stack>

      {unmatchedCounts.length > 0 ? (
        <div>
          <p className="cds--label">Unmatched by account</p>
          <Stack gap={2} orientation="horizontal">
            {unmatchedCounts.map((row) => (
              <Tag key={row.account_id} type={row.unmatched_count > 0 ? "red" : "gray"}>
                {row.account_code} {row.account_name}: {row.unmatched_count}
              </Tag>
            ))}
          </Stack>
        </div>
      ) : null}

      {canMutate ? (
        <div>
          <p className="cds--label">Upload bank CSV</p>
          <p className="cds--helper-text">
            SA bank CSV with Date, Description, and Amount (or Debit/Credit) columns. Posted to the
            selected recon account.
          </p>
          <FileUploaderDropContainer
            accept={[".csv", "text/csv"]}
            labelText="Drag and drop a CSV here or click to upload"
            multiple={false}
            disabled={uploading || !accountId}
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
            <Button
              kind="primary"
              disabled={uploading || !accountId}
              onClick={() => void handleUpload()}
            >
              {uploading ? "Uploading…" : "Import CSV"}
            </Button>
          ) : null}
        </div>
      ) : null}

      {loading ? (
        <p className="cds--type-body-01">Loading…</p>
      ) : (
        <Stack gap={4}>
          {unmatchedRows.length > 0 ? (
            <DataTable rows={unmatchedRows} headers={[...UNMATCHED_HEADERS]}>
              {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
                <TableContainer
                  title="Unmatched queue"
                  description="Lines for the selected recon account that are not yet matched."
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
                        const line = unmatchedById.get(row.id);
                        return (
                          <TableRow {...getRowProps({ row })} key={row.id}>
                            {row.cells.map((cell) => (
                              <TableCell key={cell.id}>
                                {cell.info.header === "actions" && line ? (
                                  <LineActions
                                    line={line}
                                    canMutate={canMutate}
                                    onMatch={() =>
                                      void openMatchModal(line.id, line.suggested_payment_id)
                                    }
                                    onApply={() => void openApplyModal(line)}
                                    onRecode={() => void openRecodeModal(line)}
                                  />
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
          ) : (
            <InlineNotification
              kind="info"
              title="Unmatched queue"
              subtitle="No unmatched lines for this account."
              hideCloseButton
              lowContrast
            />
          )}

          {filteredImports.length === 0 ? (
            <InlineNotification
              kind="info"
              title="No imports"
              subtitle="Upload a bank CSV against this account to begin reconciliation."
              hideCloseButton
              lowContrast
            />
          ) : (
            <>
              <Select
                id="import-select"
                labelText="Import"
                value={selectedImport?.id ?? ""}
                onChange={(event) => void handleSelectImport(event.target.value)}
              >
                {filteredImports.map((entry) => (
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
                      description={`${selectedImport.filename} — ${selectedImport.account_code} ${selectedImport.account_name}`}
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
                            const line = importLineById.get(row.id);
                            const isMatched = line ? isLineMatched(line) : false;
                            return (
                              <TableRow {...getRowProps({ row })} key={row.id}>
                                {row.cells.map((cell) => (
                                  <TableCell key={cell.id}>
                                    {cell.info.header === "status" && isMatched ? (
                                      <Tag type="green">{cell.value}</Tag>
                                    ) : cell.info.header === "status" && !isMatched ? (
                                      <Tag type="gray">{cell.value}</Tag>
                                    ) : cell.info.header === "actions" && line ? (
                                      <LineActions
                                        line={line}
                                        canMutate={canMutate}
                                        onMatch={() =>
                                          void openMatchModal(line.id, line.suggested_payment_id)
                                        }
                                        onApply={() => void openApplyModal(line)}
                                        onRecode={() => void openRecodeModal(line)}
                                      />
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
            </>
          )}
        </Stack>
      )}

      <BankRulesModal
        open={rulesOpen}
        canMutate={canMutate}
        bankAccountId={accountId}
        accounts={accounts}
        onClose={() => setRulesOpen(false)}
        onChanged={() => void refreshAfterMutation(selectedImport?.id ?? null)}
      />

      <Modal
        open={applyLine !== null}
        modalHeading="Apply bank rule"
        primaryButtonText={applying ? "Applying…" : "Apply"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={applying || !applyLine?.suggested_rule_id}
        onRequestClose={() => {
          setApplyImportId(null);
          setApplyLine(null);
        }}
        onRequestSubmit={() => void handleApplyRule()}
      >
        <p className="cds--type-body-01">
          Apply {applyLine?.suggested_rule_pattern ?? "this rule"}
          {applyLine?.suggested_account_code
            ? ` → ${applyLine.suggested_account_code} ${applyLine.suggested_account_name ?? ""}`.trimEnd()
            : ""}
          ? This posts a journal and matches the line.
        </p>
      </Modal>

      <Modal
        open={recodeLineRow !== null}
        modalHeading="Recode line"
        primaryButtonText={recoding ? "Recoding…" : "Recode"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={!recodeAccountId || recoding}
        onRequestClose={() => {
          setRecodeImportId(null);
          setRecodeLineRow(null);
          setRecodeAccountId("");
        }}
        onRequestSubmit={() => void handleRecode()}
      >
        <Select
          id="recode-account-select"
          labelText="Target account"
          helperText="Changes the non-bank side of the matched journal."
          value={recodeAccountId}
          onChange={(event) => setRecodeAccountId(event.target.value)}
        >
          <SelectItem value="" text="Select account" />
          {recodeAccounts.map((account) => (
            <SelectItem key={account.id} value={account.id} text={accountLabel(account)} />
          ))}
        </Select>
      </Modal>

      <Modal
        open={matchLineId !== null}
        modalHeading="Match line"
        primaryButtonText={matching ? "Matching…" : "Match"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={!canMatch || matching}
        onRequestClose={() => {
          setMatchImportId(null);
          setMatchLineId(null);
          setMatchPaymentId("");
          setMatchJournalId("");
        }}
        onRequestSubmit={() => void handleMatch()}
      >
        <Stack gap={4}>
          <p className="cds--helper-text">Choose a payment or a posted journal, not both.</p>
          <Select
            id="payment-select"
            labelText="Payment"
            value={matchPaymentId}
            onChange={(event) => {
              const value = event.target.value;
              setMatchPaymentId(value);
              if (value) {
                setMatchJournalId("");
              }
            }}
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
          <Select
            id="journal-select"
            labelText="Journal"
            value={matchJournalId}
            onChange={(event) => {
              const value = event.target.value;
              setMatchJournalId(value);
              if (value) {
                setMatchPaymentId("");
              }
            }}
          >
            <SelectItem value="" text="Select posted journal" />
            {postedJournals.map((journal) => (
              <SelectItem
                key={journal.id}
                value={journal.id}
                text={`${journal.journal_number ?? journal.id.slice(0, 8)} — ${formatZarAmount(journal.debit_total_zar)} on ${journal.entry_date}`}
              />
            ))}
          </Select>
        </Stack>
      </Modal>
    </Stack>
  );
}

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
  Tag,
  TextInput,
} from "@carbon/react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  canMutateBooks,
  createJournal,
  formatPriceAmount,
  formatZarAmount,
  listAccounts,
  listJournals,
  parsePriceInput,
  postJournal,
  roundHalfUp,
  voidJournal,
  type Account,
  type CreateJournalLinePayload,
  type Journal,
  type JournalStatus,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "entry_date", header: "Date" },
  { key: "journal_number", header: "Number" },
  { key: "narration", header: "Narration" },
  { key: "source", header: "Source" },
  { key: "status", header: "Status" },
  { key: "debit", header: "Debit" },
  { key: "credit", header: "Credit" },
  { key: "actions", header: "" },
] as const;

type JournalRow = {
  id: string;
  entry_date: string;
  journal_number: string;
  narration: string;
  source: string;
  status: string;
  debit: string;
  credit: string;
  actions: string;
};

type JournalLineForm = {
  account_id: string;
  debit_zar: string;
  credit_zar: string;
};

type CreateStatus = "draft" | "posted";

const emptyLine = (): JournalLineForm => ({
  account_id: "",
  debit_zar: "",
  credit_zar: "",
});

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function amountValue(raw: string): number {
  const parsed = parsePriceInput(raw);
  if (parsed === null || parsed < 0) {
    return 0;
  }
  return roundHalfUp(parsed, 2);
}

function lineIsXor(line: JournalLineForm): boolean {
  const debit = amountValue(line.debit_zar);
  const credit = amountValue(line.credit_zar);
  return (debit > 0 && credit === 0) || (credit > 0 && debit === 0);
}

function statusLabel(status: JournalStatus): string {
  if (status === "draft") {
    return "Draft";
  }
  if (status === "posted") {
    return "Posted";
  }
  return "Voided";
}

function statusTagType(status: JournalStatus): "blue" | "green" | "gray" {
  if (status === "draft") {
    return "blue";
  }
  if (status === "posted") {
    return "green";
  }
  return "gray";
}

export default function JournalsPage() {
  const { user } = useAuth();
  const canMutate = canMutateBooks(user?.role);
  const [journals, setJournals] = useState<Journal[]>([]);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [actionId, setActionId] = useState<string | null>(null);
  const [entryDate, setEntryDate] = useState(todayIso());
  const [memo, setMemo] = useState("");
  const [createStatus, setCreateStatus] = useState<CreateStatus>("posted");
  const [lines, setLines] = useState<JournalLineForm[]>([emptyLine(), emptyLine()]);
  const [viewJournal, setViewJournal] = useState<Journal | null>(null);
  const [voidTarget, setVoidTarget] = useState<Journal | null>(null);

  const journalById = useMemo(
    () => Object.fromEntries(journals.map((entry) => [entry.id, entry])),
    [journals],
  );

  const activeAccounts = useMemo(
    () => accounts.filter((account) => !account.is_archived),
    [accounts],
  );

  const loadJournals = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listJournals();
      setJournals(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load journals.");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadCreateData = useCallback(async () => {
    try {
      const data = await listAccounts();
      setAccounts(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load accounts.");
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadJournals();
    }
  }, [user, loadJournals]);

  useEffect(() => {
    if (createOpen && canMutate) {
      void loadCreateData();
    }
  }, [createOpen, canMutate, loadCreateData]);

  const totals = useMemo(() => {
    const debit = roundHalfUp(
      lines.reduce((sum, line) => sum + amountValue(line.debit_zar), 0),
      2,
    );
    const credit = roundHalfUp(
      lines.reduce((sum, line) => sum + amountValue(line.credit_zar), 0),
      2,
    );
    return { debit, credit };
  }, [lines]);

  const linesValid = lines.every((line) => line.account_id && lineIsXor(line));
  const balanced =
    totals.debit > 0 && formatPriceAmount(totals.debit) === formatPriceAmount(totals.credit);
  const formValid = Boolean(entryDate.trim()) && lines.length >= 2 && linesValid && balanced;

  function resetCreateForm() {
    setEntryDate(todayIso());
    setMemo("");
    setCreateStatus("posted");
    setLines([emptyLine(), emptyLine()]);
  }

  function updateLine(index: number, patch: Partial<JournalLineForm>) {
    setLines((current) =>
      current.map((line, lineIndex) => {
        if (lineIndex !== index) {
          return line;
        }
        const next = { ...line, ...patch };
        if (patch.debit_zar !== undefined && patch.debit_zar.trim()) {
          next.credit_zar = "";
        }
        if (patch.credit_zar !== undefined && patch.credit_zar.trim()) {
          next.debit_zar = "";
        }
        return next;
      }),
    );
  }

  function addLine() {
    setLines((current) => [...current, emptyLine()]);
  }

  function removeLine(index: number) {
    setLines((current) => (current.length > 2 ? current.filter((_, i) => i !== index) : current));
  }

  async function handleCreate() {
    if (!formValid) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createJournal({
        entry_date: entryDate.trim(),
        memo: memo.trim() || undefined,
        source: "manual",
        status: createStatus,
        lines: lines.map((line): CreateJournalLinePayload => {
          const debit = amountValue(line.debit_zar);
          const credit = amountValue(line.credit_zar);
          return {
            account_id: line.account_id,
            debit_zar: formatPriceAmount(debit),
            credit_zar: formatPriceAmount(credit),
          };
        }),
      });
      setCreateOpen(false);
      resetCreateForm();
      await loadJournals();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create journal.");
    } finally {
      setSaving(false);
    }
  }

  async function handlePost(journalId: string) {
    setActionId(journalId);
    setError(null);
    try {
      await postJournal(journalId);
      await loadJournals();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to post journal.");
    } finally {
      setActionId(null);
    }
  }

  async function handleVoid() {
    if (!voidTarget) {
      return;
    }
    setActionId(voidTarget.id);
    setError(null);
    try {
      await voidJournal(voidTarget.id);
      setVoidTarget(null);
      await loadJournals();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to void journal.");
    } finally {
      setActionId(null);
    }
  }

  const rows: JournalRow[] = journals.map((entry) => ({
    id: entry.id,
    entry_date: entry.entry_date,
    journal_number: entry.journal_number ?? "—",
    narration: entry.memo ?? "—",
    source: entry.source ?? "—",
    status: statusLabel(entry.status),
    debit: formatZarAmount(entry.debit_total_zar),
    credit: formatZarAmount(entry.credit_total_zar),
    actions: entry.id,
  }));

  return (
    <Stack gap={6}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="cds--type-productive-heading-04">Journals</h1>
          <p className="cds--type-body-01">Manual and system journal entries.</p>
        </div>
        {canMutate ? (
          <Button
            onClick={() => {
              resetCreateForm();
              setCreateOpen(true);
            }}
          >
            Create journal
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
        <p className="cds--type-body-01">Loading journals…</p>
      ) : journals.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No journals"
          subtitle="No journal entries have been posted yet."
          hideCloseButton
          lowContrast
        />
      ) : (
        <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
          {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Journals" description="General ledger journal entries">
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
                    const entry = journalById[row.id];
                    const busy = actionId === row.id;
                    return (
                      <TableRow
                        {...getRowProps({ row })}
                        key={row.id}
                        onClick={() => {
                          if (entry) {
                            setViewJournal(entry);
                          }
                        }}
                        style={{ cursor: entry ? "pointer" : undefined }}
                      >
                        {row.cells.map((cell) => {
                          if (cell.info.header === "status" && entry) {
                            return (
                              <TableCell key={cell.id}>
                                <Tag type={statusTagType(entry.status)}>
                                  {statusLabel(entry.status)}
                                </Tag>
                              </TableCell>
                            );
                          }
                          if (cell.info.header === "actions" && entry) {
                            return (
                              <TableCell key={cell.id}>
                                <Stack gap={3} orientation="horizontal">
                                  <Button
                                    kind="ghost"
                                    size="sm"
                                    onClick={(event) => {
                                      event.stopPropagation();
                                      setViewJournal(entry);
                                    }}
                                  >
                                    View
                                  </Button>
                                  {canMutate && entry.status === "draft" ? (
                                    <Button
                                      kind="ghost"
                                      size="sm"
                                      disabled={busy}
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        void handlePost(entry.id);
                                      }}
                                    >
                                      {busy ? "Posting…" : "Post"}
                                    </Button>
                                  ) : null}
                                  {canMutate &&
                                  entry.status === "posted" &&
                                  entry.document_type === "manual" ? (
                                    <Button
                                      kind="ghost"
                                      size="sm"
                                      disabled={busy}
                                      onClick={(event) => {
                                        event.stopPropagation();
                                        setVoidTarget(entry);
                                      }}
                                    >
                                      Void
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
      )}

      <Modal
        open={createOpen}
        modalHeading="Create journal"
        primaryButtonText={
          saving ? "Saving…" : createStatus === "posted" ? "Post journal" : "Save draft"
        }
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || !formValid}
        onRequestClose={() => setCreateOpen(false)}
        onRequestSubmit={() => void handleCreate()}
        size="lg"
      >
        <Stack gap={5}>
          <TextInput
            id="journal-entry-date"
            labelText="Date"
            type="date"
            value={entryDate}
            onChange={(event) => setEntryDate(event.target.value)}
            required
          />
          <TextInput
            id="journal-memo"
            labelText="Narration"
            value={memo}
            onChange={(event) => setMemo(event.target.value)}
          />
          <Select
            id="journal-status"
            labelText="Status"
            value={createStatus}
            onChange={(event) => setCreateStatus(event.target.value as CreateStatus)}
          >
            <SelectItem value="posted" text="Posted" />
            <SelectItem value="draft" text="Draft" />
          </Select>
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
                  <Select
                    id={`journal-line-account-${index}`}
                    labelText={index === 0 ? "Account" : ""}
                    hideLabel={index > 0}
                    value={line.account_id}
                    onChange={(event) => updateLine(index, { account_id: event.target.value })}
                  >
                    <SelectItem value="" text="Select an account" />
                    {activeAccounts.map((account) => (
                      <SelectItem
                        key={account.id}
                        value={account.id}
                        text={`${account.code} ${account.name}`}
                      />
                    ))}
                  </Select>
                  <TextInput
                    id={`journal-line-debit-${index}`}
                    labelText={index === 0 ? "Debit" : ""}
                    hideLabel={index > 0}
                    value={line.debit_zar}
                    onChange={(event) => updateLine(index, { debit_zar: event.target.value })}
                  />
                  <TextInput
                    id={`journal-line-credit-${index}`}
                    labelText={index === 0 ? "Credit" : ""}
                    hideLabel={index > 0}
                    value={line.credit_zar}
                    onChange={(event) => updateLine(index, { credit_zar: event.target.value })}
                  />
                  {lines.length > 2 ? (
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
          <div>
            <p className="cds--type-productive-heading-02">Totals</p>
            <p className="cds--type-body-01">Debit: R {formatPriceAmount(totals.debit)}</p>
            <p className="cds--type-body-01">Credit: R {formatPriceAmount(totals.credit)}</p>
            {!balanced && lines.length >= 2 ? (
              <p className="cds--type-body-01 cds--text-error">
                Debit and credit totals must match.
              </p>
            ) : null}
          </div>
        </Stack>
      </Modal>

      <Modal
        open={viewJournal !== null}
        modalHeading={
          viewJournal?.journal_number
            ? `Journal ${viewJournal.journal_number}`
            : "Journal details"
        }
        passiveModal
        onRequestClose={() => setViewJournal(null)}
        size="lg"
      >
        {viewJournal ? (
          <Stack gap={4}>
            <p className="cds--type-body-01">Date: {viewJournal.entry_date}</p>
            <p className="cds--type-body-01">
              Status:{" "}
              <Tag type={statusTagType(viewJournal.status)}>
                {statusLabel(viewJournal.status)}
              </Tag>
            </p>
            <p className="cds--type-body-01">Source: {viewJournal.source ?? "—"}</p>
            <p className="cds--type-body-01">Narration: {viewJournal.memo ?? "—"}</p>
            <TableContainer title="Lines">
              <Table>
                <TableHead>
                  <TableRow>
                    <TableHeader>Account</TableHeader>
                    <TableHeader>Debit</TableHeader>
                    <TableHeader>Credit</TableHeader>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {viewJournal.lines.map((line) => (
                    <TableRow key={line.id}>
                      <TableCell>
                        {line.account_code} {line.account_name}
                      </TableCell>
                      <TableCell>{formatZarAmount(line.debit_zar)}</TableCell>
                      <TableCell>{formatZarAmount(line.credit_zar)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
            <p className="cds--type-body-01">
              <strong>
                Debit {formatZarAmount(viewJournal.debit_total_zar)} · Credit{" "}
                {formatZarAmount(viewJournal.credit_total_zar)}
              </strong>
            </p>
          </Stack>
        ) : null}
      </Modal>

      <Modal
        open={voidTarget !== null}
        modalHeading="Void journal"
        primaryButtonText={actionId === voidTarget?.id ? "Voiding…" : "Void"}
        secondaryButtonText="Cancel"
        danger
        primaryButtonDisabled={actionId !== null}
        onRequestClose={() => setVoidTarget(null)}
        onRequestSubmit={() => void handleVoid()}
      >
        <p className="cds--type-body-01">
          Void <strong>{voidTarget?.journal_number ?? "this journal"}</strong>? A reversing journal
          will be posted. The original entry stays in the list as voided.
        </p>
      </Modal>
    </Stack>
  );
}

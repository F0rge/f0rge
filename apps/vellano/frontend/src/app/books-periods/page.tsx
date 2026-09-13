// Superdesign skipped — implemented Carbon from /vat201 lock/reopen pattern (CLI available).
"use client";

import {
  Button,
  DataTable,
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
  Tag,
  TextArea,
  TextInput,
} from "@carbon/react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  can,
  canMutateBooks,
  createBooksPeriod,
  lockBooksPeriod,
  listBooksPeriods,
  reopenBooksPeriod,
  type BooksPeriod,
  type BooksPeriodStatus,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "period_from", header: "From" },
  { key: "period_to", header: "To" },
  { key: "status", header: "Status" },
  { key: "actions", header: "" },
] as const;

type PeriodRow = {
  id: string;
  period_from: string;
  period_to: string;
  status: string;
  actions: string;
};

function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

function defaultMonthRange(): { from: string; to: string } {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), 1);
  const end = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  return {
    from: `${start.getFullYear()}-${pad2(start.getMonth() + 1)}-01`,
    to: `${end.getFullYear()}-${pad2(end.getMonth() + 1)}-${pad2(end.getDate())}`,
  };
}

function statusLabel(status: BooksPeriodStatus): string {
  return status === "locked" ? "Locked" : "Open";
}

function statusTagType(status: BooksPeriodStatus): "green" | "gray" {
  return status === "locked" ? "gray" : "green";
}

export default function BooksPeriodsPage() {
  const { user } = useAuth();
  const canMutate = canMutateBooks(user);
  const canReopen = can(user, "users.manage");
  const [periods, setPeriods] = useState<BooksPeriod[]>([]);
  const [fromDate, setFromDate] = useState(() => defaultMonthRange().from);
  const [toDate, setToDate] = useState(() => defaultMonthRange().to);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [lockingId, setLockingId] = useState<string | null>(null);
  const [reopenPeriod, setReopenPeriod] = useState<BooksPeriod | null>(null);
  const [reopenReason, setReopenReason] = useState("");
  const [reopening, setReopening] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const periodById = useMemo(
    () => Object.fromEntries(periods.map((period) => [period.id, period])),
    [periods],
  );

  const rows: PeriodRow[] = useMemo(
    () =>
      periods.map((period) => ({
        id: period.id,
        period_from: period.period_from,
        period_to: period.period_to,
        status: statusLabel(period.status),
        actions: period.id,
      })),
    [periods],
  );

  const loadPeriods = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listBooksPeriods();
      setPeriods(
        [...data].sort((a, b) => a.period_from.localeCompare(b.period_from)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load books periods.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadPeriods();
    }
  }, [user, loadPeriods]);

  const canCreate = Boolean(fromDate.trim() && toDate.trim());

  async function handleCreate() {
    const periodFrom = fromDate.trim();
    const periodTo = toDate.trim();
    if (!periodFrom || !periodTo) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const created = await createBooksPeriod({
        period_from: periodFrom,
        period_to: periodTo,
      });
      setPeriods((current) => {
        const without = current.filter((period) => period.id !== created.id);
        return [...without, created].sort((a, b) => a.period_from.localeCompare(b.period_from));
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create books period.");
    } finally {
      setSaving(false);
    }
  }

  async function handleLock(period: BooksPeriod) {
    if (period.status === "locked") {
      return;
    }
    setLockingId(period.id);
    setError(null);
    try {
      const locked = await lockBooksPeriod(period.id);
      setPeriods((current) =>
        current.map((entry) => (entry.id === locked.id ? locked : entry)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to lock books period.");
    } finally {
      setLockingId(null);
    }
  }

  async function handleReopen() {
    if (!reopenPeriod || !reopenReason.trim()) {
      return;
    }
    setReopening(true);
    setError(null);
    try {
      const reopened = await reopenBooksPeriod(reopenPeriod.id, reopenReason);
      setPeriods((current) =>
        current.map((entry) => (entry.id === reopened.id ? reopened : entry)),
      );
      setReopenPeriod(null);
      setReopenReason("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reopen books period.");
    } finally {
      setReopening(false);
    }
  }

  return (
    <Stack gap={6}>
      <div>
        <h1 className="cds--type-productive-heading-04">Books periods</h1>
        <p className="cds--type-body-01">
          Lock accounting periods to block GL posting (invoices, bills, payments, journals, till
          sales, layby complete). Stock receive and transfers are not locked.
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

      {canMutate ? (
        <Stack gap={4}>
          <Stack gap={4} orientation="horizontal">
            <TextInput
              id="books-period-from"
              type="date"
              labelText="Period from"
              value={fromDate}
              onChange={(event) => setFromDate(event.target.value)}
            />
            <TextInput
              id="books-period-to"
              type="date"
              labelText="Period to"
              value={toDate}
              onChange={(event) => setToDate(event.target.value)}
            />
            <Button
              kind="primary"
              disabled={saving || !canCreate}
              onClick={() => void handleCreate()}
            >
              {saving ? "Creating…" : "Create period"}
            </Button>
          </Stack>
        </Stack>
      ) : null}

      {loading ? (
        <p className="cds--type-body-01">Loading periods…</p>
      ) : periods.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No periods"
          subtitle="Create a date range to manage books period locks."
          hideCloseButton
          lowContrast
        />
      ) : (
        <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
          {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Periods">
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
                    const period = periodById[row.id];
                    return (
                      <TableRow {...getRowProps({ row })} key={row.id}>
                        {row.cells.map((cell) => {
                          if (cell.info.header === "status" && period) {
                            return (
                              <TableCell key={cell.id}>
                                <Tag type={statusTagType(period.status)}>
                                  {statusLabel(period.status)}
                                </Tag>
                              </TableCell>
                            );
                          }
                          if (cell.info.header === "actions" && period) {
                            return (
                              <TableCell key={cell.id}>
                                <Stack gap={3} orientation="horizontal">
                                  {canMutate && period.status === "open" ? (
                                    <Button
                                      kind="primary"
                                      size="sm"
                                      disabled={lockingId === period.id}
                                      onClick={() => void handleLock(period)}
                                    >
                                      {lockingId === period.id ? "Locking…" : "Lock"}
                                    </Button>
                                  ) : null}
                                  {canReopen && period.status === "locked" ? (
                                    <Button
                                      kind="danger--tertiary"
                                      size="sm"
                                      onClick={() => {
                                        setReopenReason("");
                                        setReopenPeriod(period);
                                      }}
                                    >
                                      Reopen
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
        open={reopenPeriod !== null}
        modalHeading="Reopen period"
        primaryButtonText={reopening ? "Reopening…" : "Reopen"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={reopening || !reopenReason.trim()}
        onRequestClose={() => setReopenPeriod(null)}
        onRequestSubmit={() => void handleReopen()}
      >
        <TextArea
          id="books-period-reopen-reason"
          labelText="Reason"
          value={reopenReason}
          onChange={(event) => setReopenReason(event.target.value)}
          rows={3}
        />
      </Modal>
    </Stack>
  );
}

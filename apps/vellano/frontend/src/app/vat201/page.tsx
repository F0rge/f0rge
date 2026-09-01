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
  canMutateBooks,
  createVat201Period,
  downloadVat201PeriodCsv,
  downloadVat201PeriodPdf,
  formatZarAmount,
  getVat201Period,
  listVat201Periods,
  lockVat201Period,
  reopenVat201Period,
  type Vat201Draft,
  type Vat201Period,
  type Vat201PeriodDetail,
  type Vat201PeriodStatus,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "period_from", header: "From" },
  { key: "period_to", header: "To" },
  { key: "status", header: "Status" },
] as const;

type PeriodRow = {
  id: string;
  period_from: string;
  period_to: string;
  status: string;
};

function pad2(value: number): string {
  return String(value).padStart(2, "0");
}

function defaultBimonthly(): { from: string; to: string } {
  const now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth() - 2, 1);
  const end = new Date(start.getFullYear(), start.getMonth() + 2, 0);
  return {
    from: `${start.getFullYear()}-${pad2(start.getMonth() + 1)}-01`,
    to: `${end.getFullYear()}-${pad2(end.getMonth() + 1)}-${pad2(end.getDate())}`,
  };
}

function statusLabel(status: Vat201PeriodStatus): string {
  if (status === "due") {
    return "Due";
  }
  if (status === "locked") {
    return "Locked";
  }
  return "Draft";
}

function statusTagType(status: Vat201PeriodStatus): "blue" | "red" | "gray" {
  if (status === "due") {
    return "red";
  }
  if (status === "locked") {
    return "gray";
  }
  return "blue";
}

function DraftFields({ draft }: { draft: Vat201Draft }) {
  return (
    <Stack gap={6}>
      <Stack gap={4} orientation="horizontal">
        <TextInput id="vendor-name" labelText="Vendor name" value={draft.vendor_name} readOnly />
        <TextInput
          id="vendor-vat"
          labelText="VAT number"
          value={draft.vendor_vat_number}
          readOnly
        />
      </Stack>
      <TableContainer
        title="VAT201 fields"
        description="Copy into eFiling — Field numbers match common VAT201 layout"
      >
        <Table>
          <TableHead>
            <TableRow>
              <TableHeader>Field</TableHeader>
              <TableHeader>Description</TableHeader>
              <TableHeader>Amount (ZAR)</TableHeader>
            </TableRow>
          </TableHead>
          <TableBody>
            <TableRow>
              <TableCell>1</TableCell>
              <TableCell>Standard rated supplies (excl VAT)</TableCell>
              <TableCell>
                <TextInput
                  id="field-1"
                  labelText=""
                  hideLabel
                  value={draft.standard_rated_supplies_ex_vat}
                  readOnly
                />
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell>2</TableCell>
              <TableCell>Output tax at 15%</TableCell>
              <TableCell>
                <TextInput id="field-2" labelText="" hideLabel value={draft.output_tax} readOnly />
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell>3</TableCell>
              <TableCell>Input tax</TableCell>
              <TableCell>
                <TextInput id="field-3" labelText="" hideLabel value={draft.input_tax} readOnly />
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell>4</TableCell>
              <TableCell>Net VAT payable</TableCell>
              <TableCell>
                <TextInput
                  id="field-4"
                  labelText=""
                  hideLabel
                  value={draft.net_vat_payable}
                  readOnly
                />
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </TableContainer>
      <p className="cds--type-body-01">
        Period: {draft.period_from} to {draft.period_to} — {draft.invoice_count} invoice(s),{" "}
        {draft.credit_note_count} credit note(s). Net payable:{" "}
        {formatZarAmount(draft.net_vat_payable)}
      </p>
    </Stack>
  );
}

export default function Vat201Page() {
  const { user } = useAuth();
  const canMutate = canMutateBooks(user?.role);
  const isOwner = user?.role === "owner";
  const [periods, setPeriods] = useState<Vat201Period[]>([]);
  const [selected, setSelected] = useState<Vat201PeriodDetail | null>(null);
  const [fromDate, setFromDate] = useState(() => defaultBimonthly().from);
  const [toDate, setToDate] = useState(() => defaultBimonthly().to);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [locking, setLocking] = useState(false);
  const [reopenOpen, setReopenOpen] = useState(false);
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
      })),
    [periods],
  );

  const loadPeriods = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setPeriods(await listVat201Periods());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load VAT201 periods.");
    } finally {
      setLoading(false);
    }
  }, []);

  const selectPeriod = useCallback(async (id: string) => {
    setDetailLoading(true);
    setError(null);
    try {
      setSelected(await getVat201Period(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load VAT201 period.");
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadPeriods();
    }
  }, [user, loadPeriods]);

  const canCreate = Boolean(fromDate.trim() && toDate.trim());
  const events = selected?.events;

  async function handleCreate() {
    const periodFrom = fromDate.trim();
    const periodTo = toDate.trim();
    if (!periodFrom || !periodTo) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const created = await createVat201Period({
        period_from: periodFrom,
        period_to: periodTo,
      });
      setPeriods((current) => {
        const without = current.filter((period) => period.id !== created.id);
        return [...without, created].sort((a, b) => a.period_from.localeCompare(b.period_from));
      });
      setSelected(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create VAT201 period.");
    } finally {
      setSaving(false);
    }
  }

  async function handleLock() {
    if (!selected || selected.status === "locked") {
      return;
    }
    setLocking(true);
    setError(null);
    try {
      const locked = await lockVat201Period(selected.id);
      setSelected(locked);
      setPeriods((current) =>
        current.map((period) => (period.id === locked.id ? { ...period, ...locked } : period)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to lock VAT201 period.");
    } finally {
      setLocking(false);
    }
  }

  async function handleReopen() {
    if (!selected || !reopenReason.trim()) {
      return;
    }
    setReopening(true);
    setError(null);
    try {
      const reopened = await reopenVat201Period(selected.id, reopenReason);
      setSelected(reopened);
      setPeriods((current) =>
        current.map((period) =>
          period.id === reopened.id ? { ...period, ...reopened } : period,
        ),
      );
      setReopenOpen(false);
      setReopenReason("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reopen VAT201 period.");
    } finally {
      setReopening(false);
    }
  }

  async function handleDownloadCsv() {
    if (!selected) {
      return;
    }
    try {
      await downloadVat201PeriodCsv(selected.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download CSV.");
    }
  }

  async function handleDownloadPdf() {
    if (!selected) {
      return;
    }
    try {
      await downloadVat201PeriodPdf(selected.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download PDF.");
    }
  }

  return (
    <Stack gap={6}>
      <div>
        <h1 className="cds--type-productive-heading-04">VAT201</h1>
        <p className="cds--type-body-01">
          Bi-monthly periods for manual entry into SARS eFiling. This app never files VAT or
          contacts SARS.
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

      <InlineNotification
        kind="warning"
        title="Draft only"
        subtitle="Copy these values into eFiling manually. No submission to SARS occurs from this application."
        hideCloseButton
        lowContrast
      />

      {canMutate ? (
        <Stack gap={4}>
          <Stack gap={4} orientation="horizontal">
            <TextInput
              id="vat-period-from"
              type="date"
              labelText="Period from"
              value={fromDate}
              onChange={(event) => setFromDate(event.target.value)}
            />
            <TextInput
              id="vat-period-to"
              type="date"
              labelText="Period to"
              value={toDate}
              onChange={(event) => setToDate(event.target.value)}
            />
            <Button kind="primary" disabled={saving || !canCreate} onClick={() => void handleCreate()}>
              {saving ? "Creating…" : "Create period"}
            </Button>
          </Stack>
          <p className="cds--type-helper-text-01">
            Bi-monthly, e.g. 2026-07-01 to 2026-08-31
          </p>
        </Stack>
      ) : null}

      {loading ? (
        <p className="cds--type-body-01">Loading periods…</p>
      ) : periods.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No periods"
          subtitle="Create a bi-monthly period to load a VAT201 draft."
          hideCloseButton
          lowContrast
        />
      ) : (
        <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
          {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Periods" description="Select a period to view its VAT201 draft">
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
                    const isSelected = selected?.id === row.id;
                    return (
                      <TableRow
                        {...getRowProps({ row })}
                        key={row.id}
                        onClick={() => {
                          void selectPeriod(row.id);
                        }}
                        style={{ cursor: "pointer", fontWeight: isSelected ? 600 : undefined }}
                      >
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

      {detailLoading ? <p className="cds--type-body-01">Loading draft…</p> : null}

      {selected ? (
        <Stack gap={6}>
          <DraftFields draft={selected.draft} />
          {Array.isArray(events) && events.length > 0 ? (
            <TableContainer title="History" description="Lock and reopen events">
              <Table>
                <TableHead>
                  <TableRow>
                    <TableHeader>Action</TableHeader>
                    <TableHeader>At</TableHeader>
                    <TableHeader>Reason</TableHeader>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {events.map((event, index) => (
                    <TableRow key={`${event.action}-${event.at ?? event.created_at ?? index}`}>
                      <TableCell>{event.action}</TableCell>
                      <TableCell>{event.at ?? event.created_at ?? ""}</TableCell>
                      <TableCell>{event.reason ?? ""}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          ) : null}
          <Stack gap={4} orientation="horizontal">
            <Button kind="secondary" onClick={() => void handleDownloadCsv()}>
              Download CSV
            </Button>
            <Button kind="tertiary" onClick={() => void handleDownloadPdf()}>
              Download PDF
            </Button>
            {canMutate && selected.status !== "locked" ? (
              <Button kind="primary" disabled={locking} onClick={() => void handleLock()}>
                {locking ? "Locking…" : "Lock"}
              </Button>
            ) : null}
            {isOwner && selected.status === "locked" ? (
              <Button
                kind="danger--tertiary"
                onClick={() => {
                  setReopenReason("");
                  setReopenOpen(true);
                }}
              >
                Reopen
              </Button>
            ) : null}
          </Stack>
        </Stack>
      ) : null}

      <Modal
        open={reopenOpen}
        modalHeading="Reopen period"
        primaryButtonText={reopening ? "Reopening…" : "Reopen"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={reopening || !reopenReason.trim()}
        onRequestClose={() => setReopenOpen(false)}
        onRequestSubmit={() => void handleReopen()}
      >
        <TextArea
          id="vat201-reopen-reason"
          labelText="Reason"
          value={reopenReason}
          onChange={(event) => setReopenReason(event.target.value)}
          rows={3}
        />
      </Modal>
    </Stack>
  );
}

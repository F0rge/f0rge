"use client";

import {
  Button,
  DataTable,
  InlineNotification,
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
  getReminderBoard,
  sendReminderNow,
  setCustomerReminderOptOut,
  skipReminder,
  pauseInvoiceReminders,
  resumeInvoiceReminders,
  type ReminderBoard,
  type ReminderRow,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { reminderOffsetLabel } from "@/lib/payment-reminders";

const HEADERS = [
  { key: "invoice", header: "Invoice" },
  { key: "customer", header: "Customer" },
  { key: "when", header: "When" },
  { key: "owing", header: "Amount owing" },
  { key: "status", header: "Status" },
  { key: "actions", header: "" },
];

function statusLabel(status: string): string {
  if (status === "no_email") {
    return "No email";
  }
  if (status === "opted_out") {
    return "Opted out";
  }
  if (status === "superseded") {
    return "Covered by a later reminder";
  }
  return status.replaceAll("_", " ");
}

export default function PaymentRemindersPage() {
  const { user } = useAuth();
  const canMutate = canMutateBooks(user);
  const [board, setBoard] = useState<ReminderBoard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setBoard(await getReminderBoard());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load reminders.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void load();
    }
  }, [user, load]);

  async function run(key: string, action: () => Promise<unknown>, success: string) {
    setBusyKey(key);
    setError(null);
    setNotice(null);
    try {
      await action();
      setNotice(success);
      setBoard(await getReminderBoard());
    } catch (err) {
      setError(err instanceof Error ? err.message : "That did not work.");
    } finally {
      setBusyKey(null);
    }
  }

  function rowsFor(title: string, rows: ReminderRow[], allowSend: boolean) {
    return (
      <Stack gap={3}>
        <h2 className="cds--type-productive-heading-03">{title}</h2>
        {rows.length === 0 ? (
          <p className="cds--type-body-01 firstout-muted-text">None.</p>
        ) : (
          <DataTable rows={[]} headers={[...HEADERS]}>
            {() => (
              <TableContainer>
                <Table>
                  <TableHead>
                    <TableRow>
                      {HEADERS.map((header) => (
                        <TableHeader key={header.key}>{header.header}</TableHeader>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {rows.map((row) => {
                      const key = `${row.invoice_id}-${row.offset_days}-${row.status}`;
                      return (
                        <TableRow key={key}>
                          <TableCell>{row.invoice_number}</TableCell>
                          <TableCell>
                            {row.customer_name}
                            {row.customer_email ? "" : " (no email)"}
                          </TableCell>
                          <TableCell>
                            {reminderOffsetLabel(row.offset_days)}
                            <div className="cds--type-helper-text-01">{row.trigger_on}</div>
                          </TableCell>
                          <TableCell>{formatZarAmount(row.amount_owing)}</TableCell>
                          <TableCell>
                            <Tag size="sm" type={row.status === "sent" ? "green" : "gray"}>
                              {statusLabel(row.status)}
                            </Tag>
                          </TableCell>
                          <TableCell>
                            {canMutate && allowSend ? (
                              <Stack gap={2} orientation="horizontal">
                                <Button
                                  size="sm"
                                  disabled={busyKey !== null || !row.customer_email}
                                  onClick={() =>
                                    void run(
                                      key,
                                      () => sendReminderNow(row.invoice_id, row.offset_days),
                                      `Sent the reminder for ${row.invoice_number}.`,
                                    )
                                  }
                                >
                                  Send now
                                </Button>
                                <Button
                                  size="sm"
                                  kind="ghost"
                                  disabled={busyKey !== null}
                                  onClick={() =>
                                    void run(
                                      key,
                                      () => skipReminder(row.invoice_id, row.offset_days),
                                      `Skipped the reminder for ${row.invoice_number}.`,
                                    )
                                  }
                                >
                                  Skip
                                </Button>
                                <Button
                                  size="sm"
                                  kind="ghost"
                                  disabled={busyKey !== null}
                                  onClick={() =>
                                    void run(
                                      `${key}-pause`,
                                      () =>
                                        row.reminders_paused
                                          ? resumeInvoiceReminders(row.invoice_id)
                                          : pauseInvoiceReminders(row.invoice_id),
                                      row.reminders_paused
                                        ? `Reminders resumed for ${row.invoice_number}.`
                                        : `Reminders paused for ${row.invoice_number}.`,
                                    )
                                  }
                                >
                                  {row.reminders_paused ? "Resume" : "Pause"}
                                </Button>
                              </Stack>
                            ) : null}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </DataTable>
        )}
      </Stack>
    );
  }

  return (
    <Stack gap={6}>
      <div>
        <h1 className="cds--type-productive-heading-04">Payment reminders</h1>
        <p className="cds--type-body-01">
          {board?.enabled
            ? "Automatic reminders are on. The daily job sends at most one email per invoice."
            : "Automatic reminders are off. You can still send or skip a step from this list."}
        </p>
      </div>
      {loading ? <p>Loading…</p> : null}
      {error ? (
        <InlineNotification kind="error" title="Error" subtitle={error} lowContrast hideCloseButton />
      ) : null}
      {notice ? (
        <InlineNotification
          kind="success"
          title="Done"
          subtitle={notice}
          lowContrast
          onCloseButtonClick={() => setNotice(null)}
        />
      ) : null}
      {board && board.needs_attention.length > 0 ? (
        <InlineNotification
          kind="warning"
          title="Some invoices cannot be emailed"
          subtitle={board.needs_attention
            .map((item) =>
              item.reason === "no_email"
                ? `${item.customer_name} (${item.invoice_number}) has no email`
                : `${item.invoice_number} has no due date`,
            )
            .join(". ")}
          lowContrast
          hideCloseButton
        />
      ) : null}
      {board
        ? rowsFor("Due", board.due, true)
        : null}
      {board ? rowsFor("Upcoming", board.upcoming, true) : null}
      {board ? (
        <Stack gap={3}>
          <h2 className="cds--type-productive-heading-03">Paused or opted out</h2>
          {board.held.length === 0 ? (
            <p className="cds--type-body-01 firstout-muted-text">None.</p>
          ) : (
            board.held.map((row) => (
              <Stack key={row.invoice_id} gap={2} orientation="horizontal">
                <span>
                  {row.invoice_number} · {row.customer_name} · {statusLabel(row.status)} ·{" "}
                  {formatZarAmount(row.amount_owing)} owing
                </span>
                {canMutate ? (
                  <>
                    <Button
                      size="sm"
                      kind="ghost"
                      disabled={busyKey !== null}
                      onClick={() =>
                        void run(
                          `held-${row.invoice_id}`,
                          () =>
                            row.reminders_paused
                              ? resumeInvoiceReminders(row.invoice_id)
                              : pauseInvoiceReminders(row.invoice_id),
                          "Updated.",
                        )
                      }
                    >
                      {row.status === "paused" ? "Resume invoice" : "Pause invoice"}
                    </Button>
                    <Button
                      size="sm"
                      kind="ghost"
                      disabled={busyKey !== null}
                      onClick={() =>
                        void run(
                          `opt-${row.customer_id}`,
                          () =>
                            setCustomerReminderOptOut(
                              row.customer_id,
                              !row.payment_reminders_opt_out,
                            ),
                          row.payment_reminders_opt_out
                            ? "Customer will receive reminders again."
                            : "Customer opted out.",
                        )
                      }
                    >
                      {row.payment_reminders_opt_out ? "Opt back in" : "Opt customer out"}
                    </Button>
                  </>
                ) : null}
              </Stack>
            ))
          )}
        </Stack>
      ) : null}
      {board ? rowsFor("Sent and skipped", board.sent, false) : null}
    </Stack>
  );
}

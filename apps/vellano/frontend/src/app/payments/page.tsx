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
} from "@carbon/react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { BooksHistory } from "@/components/books-history";
import {
  downloadPaymentPdf,
  formatFxGainLoss,
  formatZarAmount,
  listPayments,
  type Payment,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "payment_number", header: "Number" },
  { key: "direction", header: "Direction" },
  { key: "amount", header: "Amount" },
  { key: "currency", header: "Currency" },
  { key: "amount_zar", header: "ZAR" },
  { key: "fx_gain_loss_zar", header: "FX gain/loss" },
  { key: "paid_on", header: "Paid on" },
  { key: "actions", header: "" },
] as const;

type PaymentRow = {
  id: string;
  payment_number: string;
  direction: string;
  amount: string;
  currency: string;
  amount_zar: string;
  fx_gain_loss_zar: string;
  paid_on: string;
  actions: string;
};

export default function PaymentsPage() {
  const { user } = useAuth();
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [historyPayment, setHistoryPayment] = useState<Payment | null>(null);

  const loadPayments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listPayments();
      setPayments(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load payments.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadPayments();
    }
  }, [user, loadPayments]);

  const paymentById = useMemo(
    () => Object.fromEntries(payments.map((entry) => [entry.id, entry])),
    [payments],
  );

  async function handleDownload(paymentId: string, paymentNumber: string) {
    setError(null);
    try {
      await downloadPaymentPdf(paymentId, paymentNumber);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download payment receipt.");
    }
  }

  const rows: PaymentRow[] = payments.map((entry) => ({
    id: entry.id,
    payment_number: entry.payment_number,
    direction: entry.direction === "in" ? "In" : "Out",
    amount: entry.amount,
    currency: entry.currency,
    amount_zar: formatZarAmount(entry.amount_zar),
    fx_gain_loss_zar: formatFxGainLoss(entry.fx_gain_loss_zar),
    paid_on: entry.paid_on,
    actions: entry.id,
  }));

  return (
    <Stack gap={6}>
      <div>
        <h1 className="cds--type-productive-heading-04">Payments</h1>
        <p className="cds--type-body-01">
          Recorded cash movements — record new payments from invoice or bill detail.
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

      {loading ? (
        <p className="cds--type-body-01">Loading payments…</p>
      ) : payments.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No payments"
          subtitle="No payments have been recorded yet."
          hideCloseButton
          lowContrast
        />
      ) : (
        <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
          {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Payments" description="All recorded payments">
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
                    const payment = paymentById[row.id];
                    return (
                      <TableRow
                        {...getRowProps({ row })}
                        key={row.id}
                        onClick={() => {
                          if (payment) {
                            setHistoryPayment(payment);
                          }
                        }}
                        style={{ cursor: payment ? "pointer" : undefined }}
                      >
                        {row.cells.map((cell) => {
                          if (cell.info.header === "actions" && payment) {
                            return (
                              <TableCell key={cell.id}>
                                <Button
                                  kind="ghost"
                                  size="sm"
                                  onClick={(event) => {
                                    event.stopPropagation();
                                    void handleDownload(payment.id, payment.payment_number);
                                  }}
                                >
                                  Download receipt
                                </Button>
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
        open={historyPayment !== null}
        modalHeading={
          historyPayment ? `Payment ${historyPayment.payment_number}` : "History"
        }
        passiveModal
        onRequestClose={() => setHistoryPayment(null)}
        size="md"
      >
        {historyPayment ? (
          <BooksHistory documentType="payment" documentId={historyPayment.id} />
        ) : null}
      </Modal>
    </Stack>
  );
}

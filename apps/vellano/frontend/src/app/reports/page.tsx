"use client";

import {
  Button,
  DataTable,
  DatePicker,
  DatePickerInput,
  InlineNotification,
  Stack,
  Tab,
  TabList,
  TabPanel,
  TabPanels,
  Tabs,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
} from "@carbon/react";
import { useCallback, useEffect, useState } from "react";

import {
  formatZarAmount,
  getAgedAp,
  getAgedAr,
  getBalanceSheet,
  getProfitLoss,
  type AgedReport,
  type BalanceSheetReport,
  type ProfitLossReport,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function monthStartIso(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
}

const AGED_HEADERS = [
  { key: "document_number", header: "Document" },
  { key: "contact_name", header: "Contact" },
  { key: "issue_date", header: "Issue date" },
  { key: "days_outstanding", header: "Days" },
  { key: "bucket", header: "Bucket" },
  { key: "balance_zar", header: "Balance" },
] as const;

export default function ReportsPage() {
  const { user } = useAuth();
  const [asOf, setAsOf] = useState(todayIso());
  const [fromDate, setFromDate] = useState(monthStartIso());
  const [toDate, setToDate] = useState(todayIso());
  const [agedAr, setAgedAr] = useState<AgedReport | null>(null);
  const [agedAp, setAgedAp] = useState<AgedReport | null>(null);
  const [profitLoss, setProfitLoss] = useState<ProfitLossReport | null>(null);
  const [balanceSheet, setBalanceSheet] = useState<BalanceSheetReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadReports = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [ar, ap, pl, bs] = await Promise.all([
        getAgedAr(asOf),
        getAgedAp(asOf),
        getProfitLoss(fromDate, toDate),
        getBalanceSheet(asOf),
      ]);
      setAgedAr(ar);
      setAgedAp(ap);
      setProfitLoss(pl);
      setBalanceSheet(bs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load reports.");
    } finally {
      setLoading(false);
    }
  }, [asOf, fromDate, toDate]);

  useEffect(() => {
    if (user) {
      void loadReports();
    }
  }, [user, loadReports]);

  function agedRows(report: AgedReport | null) {
    return (
      report?.lines.map((line) => ({
        id: line.document_number,
        document_number: line.document_number,
        contact_name: line.contact_name,
        issue_date: line.issue_date,
        days_outstanding: String(line.days_outstanding),
        bucket: line.bucket,
        balance_zar: formatZarAmount(line.balance_zar),
      })) ?? []
    );
  }

  return (
    <Stack gap={6}>
      <div>
        <h1 className="cds--type-productive-heading-04">Reports</h1>
        <p className="cds--type-body-01">
          Aged receivables and payables, profit &amp; loss, and balance sheet in ZAR.
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

      <Stack gap={4} orientation="horizontal">
        <DatePicker datePickerType="single" dateFormat="Y-m-d" value={asOf}>
          <DatePickerInput
            id="as-of"
            labelText="As of (aged AR/AP, balance sheet)"
            placeholder="YYYY-MM-DD"
            onChange={(event) => setAsOf(event.target.value)}
          />
        </DatePicker>
        <DatePicker datePickerType="single" dateFormat="Y-m-d" value={fromDate}>
          <DatePickerInput
            id="from-date"
            labelText="P&L from"
            placeholder="YYYY-MM-DD"
            onChange={(event) => setFromDate(event.target.value)}
          />
        </DatePicker>
        <DatePicker datePickerType="single" dateFormat="Y-m-d" value={toDate}>
          <DatePickerInput
            id="to-date"
            labelText="P&L to"
            placeholder="YYYY-MM-DD"
            onChange={(event) => setToDate(event.target.value)}
          />
        </DatePicker>
        <Button kind="primary" disabled={loading} onClick={() => void loadReports()}>
          {loading ? "Loading…" : "Refresh"}
        </Button>
      </Stack>

      <Tabs>
        <TabList aria-label="Financial reports">
          <Tab>Aged AR</Tab>
          <Tab>Aged AP</Tab>
          <Tab>Profit &amp; loss</Tab>
          <Tab>Balance sheet</Tab>
        </TabList>
        <TabPanels>
          <TabPanel>
            {agedAr ? (
              <Stack gap={4}>
                <p className="cds--type-body-01">
                  Total outstanding: {formatZarAmount(agedAr.total_zar)}
                </p>
                <DataTable rows={agedRows(agedAr)} headers={[...AGED_HEADERS]}>
                  {({ rows, headers, getTableProps, getHeaderProps, getRowProps }) => (
                    <TableContainer title="Aged accounts receivable">
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
                          {rows.map((row) => (
                            <TableRow {...getRowProps({ row })} key={row.id}>
                              {row.cells.map((cell) => (
                                <TableCell key={cell.id}>{cell.value}</TableCell>
                              ))}
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  )}
                </DataTable>
              </Stack>
            ) : null}
          </TabPanel>
          <TabPanel>
            {agedAp ? (
              <Stack gap={4}>
                <p className="cds--type-body-01">
                  Total outstanding: {formatZarAmount(agedAp.total_zar)}
                </p>
                <DataTable rows={agedRows(agedAp)} headers={[...AGED_HEADERS]}>
                  {({ rows, headers, getTableProps, getHeaderProps, getRowProps }) => (
                    <TableContainer title="Aged accounts payable">
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
                          {rows.map((row) => (
                            <TableRow {...getRowProps({ row })} key={row.id}>
                              {row.cells.map((cell) => (
                                <TableCell key={cell.id}>{cell.value}</TableCell>
                              ))}
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </TableContainer>
                  )}
                </DataTable>
              </Stack>
            ) : null}
          </TabPanel>
          <TabPanel>
            {profitLoss ? (
              <Stack gap={4}>
                <p className="cds--type-body-01">
                  Net profit: {formatZarAmount(profitLoss.net_profit_zar)} (
                  {profitLoss.from_date} to {profitLoss.to_date})
                </p>
                <TableContainer title="Income">
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableHeader>Code</TableHeader>
                        <TableHeader>Account</TableHeader>
                        <TableHeader>Amount</TableHeader>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {profitLoss.income.map((line) => (
                        <TableRow key={line.code}>
                          <TableCell>{line.code}</TableCell>
                          <TableCell>{line.name}</TableCell>
                          <TableCell>{formatZarAmount(line.amount_zar)}</TableCell>
                        </TableRow>
                      ))}
                      <TableRow>
                        <TableCell colSpan={2}>
                          <strong>Total income</strong>
                        </TableCell>
                        <TableCell>
                          <strong>{formatZarAmount(profitLoss.total_income_zar)}</strong>
                        </TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </TableContainer>
                <TableContainer title="Expenses">
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableHeader>Code</TableHeader>
                        <TableHeader>Account</TableHeader>
                        <TableHeader>Amount</TableHeader>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {profitLoss.expenses.map((line) => (
                        <TableRow key={line.code}>
                          <TableCell>{line.code}</TableCell>
                          <TableCell>{line.name}</TableCell>
                          <TableCell>{formatZarAmount(line.amount_zar)}</TableCell>
                        </TableRow>
                      ))}
                      <TableRow>
                        <TableCell colSpan={2}>
                          <strong>Total expenses</strong>
                        </TableCell>
                        <TableCell>
                          <strong>{formatZarAmount(profitLoss.total_expenses_zar)}</strong>
                        </TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </TableContainer>
              </Stack>
            ) : null}
          </TabPanel>
          <TabPanel>
            {balanceSheet ? (
              <Stack gap={4}>
                <p className="cds--type-body-01">
                  As of {balanceSheet.as_of} — Equity: {formatZarAmount(balanceSheet.equity_zar)}
                </p>
                <TableContainer title="Assets">
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableHeader>Code</TableHeader>
                        <TableHeader>Account</TableHeader>
                        <TableHeader>Balance</TableHeader>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {balanceSheet.assets.map((line) => (
                        <TableRow key={line.code}>
                          <TableCell>{line.code}</TableCell>
                          <TableCell>{line.name}</TableCell>
                          <TableCell>{formatZarAmount(line.balance_zar)}</TableCell>
                        </TableRow>
                      ))}
                      <TableRow>
                        <TableCell colSpan={2}>
                          <strong>Total assets</strong>
                        </TableCell>
                        <TableCell>
                          <strong>{formatZarAmount(balanceSheet.total_assets_zar)}</strong>
                        </TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </TableContainer>
                <TableContainer title="Liabilities">
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableHeader>Code</TableHeader>
                        <TableHeader>Account</TableHeader>
                        <TableHeader>Balance</TableHeader>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {balanceSheet.liabilities.map((line) => (
                        <TableRow key={line.code}>
                          <TableCell>{line.code}</TableCell>
                          <TableCell>{line.name}</TableCell>
                          <TableCell>{formatZarAmount(line.balance_zar)}</TableCell>
                        </TableRow>
                      ))}
                      <TableRow>
                        <TableCell colSpan={2}>
                          <strong>Total liabilities</strong>
                        </TableCell>
                        <TableCell>
                          <strong>{formatZarAmount(balanceSheet.total_liabilities_zar)}</strong>
                        </TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </TableContainer>
              </Stack>
            ) : null}
          </TabPanel>
        </TabPanels>
      </Tabs>
    </Stack>
  );
}

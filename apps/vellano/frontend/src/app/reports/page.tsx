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
  TextInput,
} from "@carbon/react";
import { useCallback, useEffect, useRef, useState } from "react";

import { CriticalityReport } from "@/components/criticality-report";
import { LeadTimesReport } from "@/components/lead-times-report";
import {
  downloadAgedStockCsv,
  downloadCashSummaryCsv,
  downloadJournalsCsv,
  downloadSalesBySkuCsv,
  downloadSalesVatCsv,
  downloadStockValuationCsv,
  downloadTrialBalanceCsv,
  formatZarAmount,
  getAgedAp,
  getAgedAr,
  getAgedStock,
  getBalanceSheet,
  getCashSummary,
  getJournalsReport,
  getProfitLoss,
  getSalesBySku,
  getSalesVat,
  getSkuCriticality,
  getSkuLeadTimes,
  getStockValuation,
  getSupplierLeadTimes,
  getTrialBalance,
  type AgedReport,
  type AgedStockReport,
  type BalanceSheetReport,
  type CashSummaryReport,
  type JournalReport,
  type ProfitLossReport,
  type SalesBySkuReport,
  type SalesVatReport,
  type SkuCriticalityReport,
  type SkuLeadTimesReport,
  type StockValuationReport,
  type SupplierLeadTimesReport,
  type TrialBalanceReport,
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

const STOCK_VALUATION_HEADERS = [
  { key: "location_name", header: "Location" },
  { key: "our_ref", header: "Our ref" },
  { key: "name", header: "Name" },
  { key: "on_hand", header: "On hand" },
  { key: "unit_cost_zar", header: "Unit cost" },
  { key: "value_zar", header: "Value" },
] as const;

const AGED_STOCK_HEADERS = [
  { key: "our_ref", header: "Our ref" },
  { key: "location_name", header: "Location" },
  { key: "on_hand", header: "On hand" },
  { key: "days", header: "Days" },
  { key: "bucket", header: "Bucket" },
  { key: "value_zar", header: "Value" },
] as const;

const SALES_BY_SKU_HEADERS = [
  { key: "our_ref", header: "Our ref" },
  { key: "name", header: "Name" },
  { key: "qty", header: "Qty" },
  { key: "ex_vat_zar", header: "Ex VAT" },
  { key: "inc_vat_zar", header: "Inc VAT" },
] as const;

const TRIAL_BALANCE_HEADERS = [
  { key: "code", header: "Code" },
  { key: "name", header: "Account" },
  { key: "debit_zar", header: "Debit" },
  { key: "credit_zar", header: "Credit" },
] as const;

const JOURNAL_REPORT_HEADERS = [
  { key: "entry_date", header: "Date" },
  { key: "journal_number", header: "Number" },
  { key: "document_type", header: "Type" },
  { key: "source", header: "Source" },
  { key: "memo", header: "Memo" },
  { key: "status", header: "Status" },
  { key: "account_code", header: "Account" },
  { key: "account_name", header: "Name" },
  { key: "debit_zar", header: "Debit" },
  { key: "credit_zar", header: "Credit" },
] as const;

const CASH_SUMMARY_HEADERS = [
  { key: "code", header: "Code" },
  { key: "name", header: "Account" },
  { key: "cash_in_zar", header: "Cash in" },
  { key: "cash_out_zar", header: "Cash out" },
  { key: "net_zar", header: "Net" },
] as const;

export default function ReportsPage() {
  const { user } = useAuth();
  const [asOf, setAsOf] = useState(todayIso());
  const [fromDate, setFromDate] = useState(monthStartIso());
  const [toDate, setToDate] = useState(todayIso());
  const [journalSource, setJournalSource] = useState("");
  const journalSourceRef = useRef(journalSource);
  journalSourceRef.current = journalSource;
  const [agedAr, setAgedAr] = useState<AgedReport | null>(null);
  const [agedAp, setAgedAp] = useState<AgedReport | null>(null);
  const [profitLoss, setProfitLoss] = useState<ProfitLossReport | null>(null);
  const [balanceSheet, setBalanceSheet] = useState<BalanceSheetReport | null>(null);
  const [trialBalance, setTrialBalance] = useState<TrialBalanceReport | null>(null);
  const [journalsReport, setJournalsReport] = useState<JournalReport | null>(null);
  const [cashSummary, setCashSummary] = useState<CashSummaryReport | null>(null);
  const [stockValuation, setStockValuation] = useState<StockValuationReport | null>(null);
  const [agedStock, setAgedStock] = useState<AgedStockReport | null>(null);
  const [salesBySku, setSalesBySku] = useState<SalesBySkuReport | null>(null);
  const [salesVat, setSalesVat] = useState<SalesVatReport | null>(null);
  const [supplierLeadTimes, setSupplierLeadTimes] = useState<SupplierLeadTimesReport | null>(null);
  const [skuLeadTimes, setSkuLeadTimes] = useState<SkuLeadTimesReport | null>(null);
  const [skuCriticality, setSkuCriticality] = useState<SkuCriticalityReport | null>(null);
  const [leadTimesError, setLeadTimesError] = useState<string | null>(null);
  const [criticalityError, setCriticalityError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadReports = useCallback(async () => {
    const effectiveAsOf = asOf.trim() || todayIso();
    const effectiveFrom = fromDate.trim() || monthStartIso();
    const effectiveTo = toDate.trim() || todayIso();

    if (!asOf.trim()) setAsOf(effectiveAsOf);
    if (!fromDate.trim()) setFromDate(effectiveFrom);
    if (!toDate.trim()) setToDate(effectiveTo);

    setLoading(true);
    setError(null);
    setLeadTimesError(null);
    setCriticalityError(null);
    try {
      const [ar, ap, pl, bs, tb, journals, cash, valuation, aged, salesSku, salesVatReport] =
        await Promise.all([
          getAgedAr(effectiveAsOf),
          getAgedAp(effectiveAsOf),
          getProfitLoss(effectiveFrom, effectiveTo),
          getBalanceSheet(effectiveAsOf),
          getTrialBalance(effectiveAsOf),
          getJournalsReport(effectiveFrom, effectiveTo, journalSourceRef.current),
          getCashSummary(effectiveFrom, effectiveTo),
          getStockValuation(),
          getAgedStock(),
          getSalesBySku(effectiveFrom, effectiveTo),
          getSalesVat(effectiveFrom, effectiveTo),
        ]);
      setAgedAr(ar);
      setAgedAp(ap);
      setProfitLoss(pl);
      setBalanceSheet(bs);
      setTrialBalance(tb);
      setJournalsReport(journals);
      setCashSummary(cash);
      setStockValuation(valuation);
      setAgedStock(aged);
      setSalesBySku(salesSku);
      setSalesVat(salesVatReport);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load reports.");
    }

    try {
      const [supplierLead, skuLead] = await Promise.all([
        getSupplierLeadTimes(),
        getSkuLeadTimes(),
      ]);
      setSupplierLeadTimes(supplierLead);
      setSkuLeadTimes(skuLead);
    } catch (err) {
      setSupplierLeadTimes({ rows: [] });
      setSkuLeadTimes({ rows: [] });
      setLeadTimesError(err instanceof Error ? err.message : "Failed to load lead times.");
    }

    try {
      const criticality = await getSkuCriticality(effectiveFrom, effectiveTo);
      setSkuCriticality(criticality);
    } catch (err) {
      setSkuCriticality(null);
      setCriticalityError(err instanceof Error ? err.message : "Failed to load criticality.");
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

  async function handleCsvDownload(download: () => Promise<void>) {
    try {
      await download();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download CSV.");
    }
  }

  function stockValuationRows(report: StockValuationReport | null) {
    return (
      report?.lines.map((line) => ({
        id: `${line.location_id}-${line.sku_id}`,
        location_name: line.location_name,
        our_ref: line.our_ref,
        name: line.name,
        on_hand: String(line.on_hand),
        unit_cost_zar: formatZarAmount(line.unit_cost_zar),
        value_zar: formatZarAmount(line.value_zar),
      })) ?? []
    );
  }

  function agedStockRows(report: AgedStockReport | null) {
    const lines = report?.buckets.flatMap((bucket) => bucket.lines) ?? [];
    return lines.map((line) => ({
      id: `${line.sku_id}-${line.location_id}`,
      our_ref: line.our_ref,
      location_name: line.location_name,
      on_hand: String(line.on_hand),
      days: String(line.days),
      bucket: line.bucket,
      value_zar: formatZarAmount(line.value_zar),
    }));
  }

  function salesBySkuRows(report: SalesBySkuReport | null) {
    return (
      report?.lines.map((line) => ({
        id: line.sku_id,
        our_ref: line.our_ref,
        name: line.name,
        qty: String(line.qty),
        ex_vat_zar: formatZarAmount(line.ex_vat_zar),
        inc_vat_zar: formatZarAmount(line.inc_vat_zar),
      })) ?? []
    );
  }

  function trialBalanceRows(report: TrialBalanceReport | null) {
    return (
      report?.lines.map((line) => ({
        id: line.code,
        code: line.code,
        name: line.name,
        debit_zar: formatZarAmount(line.debit_zar),
        credit_zar: formatZarAmount(line.credit_zar),
      })) ?? []
    );
  }

  function journalReportRows(report: JournalReport | null) {
    return (
      report?.entries.flatMap((entry, entryIndex) =>
        entry.lines.map((line, lineIndex) => ({
          id: `${entry.journal_number ?? "journal"}-${entryIndex}-${lineIndex}`,
          entry_date: entry.entry_date,
          journal_number: entry.journal_number ?? "",
          document_type: entry.document_type,
          source: entry.source ?? "",
          memo: entry.memo ?? "",
          status: entry.status,
          account_code: line.account_code,
          account_name: line.account_name,
          debit_zar: formatZarAmount(line.debit_zar),
          credit_zar: formatZarAmount(line.credit_zar),
        })),
      ) ?? []
    );
  }

  function cashSummaryRows(report: CashSummaryReport | null) {
    return (
      report?.accounts.map((account) => ({
        id: account.code,
        code: account.code,
        name: account.name,
        cash_in_zar: formatZarAmount(account.cash_in_zar),
        cash_out_zar: formatZarAmount(account.cash_out_zar),
        net_zar: formatZarAmount(account.net_zar),
      })) ?? []
    );
  }

  return (
    <Stack gap={6}>
      <div>
        <h1 className="cds--type-productive-heading-04">Reports</h1>
        <p className="cds--type-body-01">
          Financial and stock reports in ZAR — aged AR/AP, P&amp;L, balance sheet, trial balance,
          journals, cash summary, stock valuation, aged stock, sales, lead times, and criticality.
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
            labelText="As of (aged AR/AP, balance sheet, trial balance)"
            placeholder="YYYY-MM-DD"
            onChange={(event) => setAsOf(event.target.value)}
          />
        </DatePicker>
        <DatePicker datePickerType="single" dateFormat="Y-m-d" value={fromDate}>
          <DatePickerInput
            id="from-date"
            labelText="From (P&L, sales, journals, cash)"
            placeholder="YYYY-MM-DD"
            onChange={(event) => setFromDate(event.target.value)}
          />
        </DatePicker>
        <DatePicker datePickerType="single" dateFormat="Y-m-d" value={toDate}>
          <DatePickerInput
            id="to-date"
            labelText="To (P&L, sales, journals, cash)"
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
          <Tab>Trial balance</Tab>
          <Tab>Journals</Tab>
          <Tab>Cash summary</Tab>
          <Tab>Stock valuation</Tab>
          <Tab>Aged stock</Tab>
          <Tab>Sales by SKU</Tab>
          <Tab>Lead times</Tab>
          <Tab>Criticality</Tab>
          <Tab>Sales VAT</Tab>
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
                <p className="cds--type-body-01">
                  Income and expenses are grouped by account, including category sales.
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
          <TabPanel>
            {trialBalance ? (
              <Stack gap={4}>
                <Stack gap={4} orientation="horizontal">
                  <p className="cds--type-body-01">
                    As of {trialBalance.as_of} — Debits {formatZarAmount(trialBalance.total_debit_zar)}{" "}
                    / Credits {formatZarAmount(trialBalance.total_credit_zar)}
                  </p>
                  <Button
                    kind="tertiary"
                    onClick={() => void handleCsvDownload(() => downloadTrialBalanceCsv(asOf))}
                  >
                    Download CSV
                  </Button>
                </Stack>
                <DataTable rows={trialBalanceRows(trialBalance)} headers={[...TRIAL_BALANCE_HEADERS]}>
                  {({ rows, headers, getTableProps, getHeaderProps, getRowProps }) => (
                    <TableContainer title="Trial balance">
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
            {journalsReport ? (
              <Stack gap={4}>
                <TextInput
                  id="journal-source"
                  labelText="Source (optional)"
                  placeholder="e.g. manual"
                  helperText="Leave blank for all sources. Click Refresh to apply."
                  value={journalSource}
                  onChange={(event) => setJournalSource(event.target.value)}
                />
                <Stack gap={4} orientation="horizontal">
                  <p className="cds--type-body-01">
                    {journalsReport.from_date} to {journalsReport.to_date}
                    {journalsReport.source ? ` — source ${journalsReport.source}` : ""}
                  </p>
                  <Button
                    kind="tertiary"
                    onClick={() =>
                      void handleCsvDownload(() =>
                        downloadJournalsCsv(fromDate, toDate, journalSource),
                      )
                    }
                  >
                    Download CSV
                  </Button>
                </Stack>
                <DataTable
                  rows={journalReportRows(journalsReport)}
                  headers={[...JOURNAL_REPORT_HEADERS]}
                >
                  {({ rows, headers, getTableProps, getHeaderProps, getRowProps }) => (
                    <TableContainer title="Journals">
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
            {cashSummary ? (
              <Stack gap={4}>
                <Stack gap={4} orientation="horizontal">
                  <p className="cds--type-body-01">
                    {cashSummary.from_date} to {cashSummary.to_date} — In{" "}
                    {formatZarAmount(cashSummary.total_cash_in_zar)} / Out{" "}
                    {formatZarAmount(cashSummary.total_cash_out_zar)} / Net{" "}
                    {formatZarAmount(cashSummary.total_net_zar)}
                  </p>
                  <Button
                    kind="tertiary"
                    onClick={() =>
                      void handleCsvDownload(() => downloadCashSummaryCsv(fromDate, toDate))
                    }
                  >
                    Download CSV
                  </Button>
                </Stack>
                <DataTable rows={cashSummaryRows(cashSummary)} headers={[...CASH_SUMMARY_HEADERS]}>
                  {({ rows, headers, getTableProps, getHeaderProps, getRowProps }) => (
                    <TableContainer title="Cash summary">
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
            {stockValuation ? (
              <Stack gap={4}>
                <Stack gap={4} orientation="horizontal">
                  <p className="cds--type-body-01">
                    Total inventory value: {formatZarAmount(stockValuation.total_value_zar)}
                  </p>
                  <Button
                    kind="tertiary"
                    onClick={() => void handleCsvDownload(downloadStockValuationCsv)}
                  >
                    Download CSV
                  </Button>
                </Stack>
                <DataTable
                  rows={stockValuationRows(stockValuation)}
                  headers={[...STOCK_VALUATION_HEADERS]}
                >
                  {({ rows, headers, getTableProps, getHeaderProps, getRowProps }) => (
                    <TableContainer title="Stock valuation">
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
            {agedStock ? (
              <Stack gap={4}>
                <Stack gap={4} orientation="horizontal">
                  <p className="cds--type-body-01">Current snapshot by age bucket.</p>
                  <Button
                    kind="tertiary"
                    onClick={() => void handleCsvDownload(downloadAgedStockCsv)}
                  >
                    Download CSV
                  </Button>
                </Stack>
                <TableContainer title="Age buckets">
                  <Table>
                    <TableHead>
                      <TableRow>
                        <TableHeader>Bucket</TableHeader>
                        <TableHeader>Qty</TableHeader>
                        <TableHeader>Value</TableHeader>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {agedStock.buckets.map((bucket) => (
                        <TableRow key={bucket.bucket}>
                          <TableCell>{bucket.label}</TableCell>
                          <TableCell>{bucket.qty}</TableCell>
                          <TableCell>{formatZarAmount(bucket.value_zar)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
                <DataTable rows={agedStockRows(agedStock)} headers={[...AGED_STOCK_HEADERS]}>
                  {({ rows, headers, getTableProps, getHeaderProps, getRowProps }) => (
                    <TableContainer title="Aged stock detail">
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
            {salesBySku ? (
              <Stack gap={4}>
                <Stack gap={4} orientation="horizontal">
                  <p className="cds--type-body-01">
                    {salesBySku.from_date} to {salesBySku.to_date}
                  </p>
                  <Button
                    kind="tertiary"
                    onClick={() =>
                      void handleCsvDownload(() =>
                        downloadSalesBySkuCsv(fromDate, toDate),
                      )
                    }
                  >
                    Download CSV
                  </Button>
                </Stack>
                <DataTable rows={salesBySkuRows(salesBySku)} headers={[...SALES_BY_SKU_HEADERS]}>
                  {({ rows, headers, getTableProps, getHeaderProps, getRowProps }) => (
                    <TableContainer title="Sales by SKU">
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
            {supplierLeadTimes && skuLeadTimes ? (
              <LeadTimesReport
                suppliers={supplierLeadTimes.rows}
                skus={skuLeadTimes.rows}
                error={leadTimesError}
                onCsvError={setError}
              />
            ) : null}
          </TabPanel>
          <TabPanel>
            {skuCriticality ? (
              <CriticalityReport
                report={skuCriticality}
                fromDate={fromDate}
                toDate={toDate}
                error={criticalityError}
                onCsvError={setError}
              />
            ) : criticalityError ? (
              <InlineNotification
                kind="error"
                title="Criticality"
                subtitle={criticalityError}
                hideCloseButton
                lowContrast
              />
            ) : null}
          </TabPanel>
          <TabPanel>
            {salesVat ? (
              <Stack gap={4}>
                <Stack gap={4} orientation="horizontal">
                  <p className="cds--type-body-01">
                    {salesVat.from_date} to {salesVat.to_date}
                  </p>
                  <Button
                    kind="tertiary"
                    onClick={() =>
                      void handleCsvDownload(() => downloadSalesVatCsv(fromDate, toDate))
                    }
                  >
                    Download CSV
                  </Button>
                </Stack>
                <TableContainer title="Sales VAT summary">
                  <Table>
                    <TableBody>
                      <TableRow>
                        <TableCell>Invoices</TableCell>
                        <TableCell>{salesVat.invoice_count}</TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>Subtotal (ex VAT)</TableCell>
                        <TableCell>{formatZarAmount(salesVat.subtotal_ex_vat)}</TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>VAT amount</TableCell>
                        <TableCell>{formatZarAmount(salesVat.vat_amount)}</TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>Total (inc VAT)</TableCell>
                        <TableCell>{formatZarAmount(salesVat.total_inc_vat)}</TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell>Amount paid</TableCell>
                        <TableCell>{formatZarAmount(salesVat.amount_paid)}</TableCell>
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

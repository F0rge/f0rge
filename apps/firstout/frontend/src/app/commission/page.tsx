"use client";

import { Download } from "@carbon/icons-react";
import {
  Button, DataTableSkeleton, InlineNotification, Modal, Select, SelectItem, Stack,
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@carbon/react";
import Link from "next/link";
import { useEffect, useState } from "react";
import metrics from "@/components/staff-metrics.module.css";
import {
  ApiError, can, getCommissionReport, listSalesStaffOptions, updateInvoiceSalesStaff,
  type CommissionReport, type CommissionRow, type SalesStaffOption,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { downloadCsv } from "@/lib/csv";
import { COMMISSION_CSV_HEADERS, commissionCsvRows, recentMonths, zar } from "@/lib/sales-staff";

const message = (error: unknown, fallback: string) => (error instanceof ApiError ? error.message : fallback);
const rowKey = (row: CommissionRow) => row.sales_staff_id ?? "unattributed";

function CommissionScreen({ canAssign }: { canAssign: boolean }) {
  const [months] = useState(() => recentMonths());
  const [month, setMonth] = useState(months[0].value);
  // Keyed by month so a month change shows loading until its own report arrives.
  const [result, setResult] = useState<{ month: string; report?: CommissionReport; error?: string } | null>(null);
  const [openKey, setOpenKey] = useState<string | null>(null);
  const [colleagues, setColleagues] = useState<SalesStaffOption[]>([]);
  const [notice, setNotice] = useState("");
  const [assignError, setAssignError] = useState("");

  const [reloads, setReloads] = useState(0);
  const current = result?.month === month ? result : null;
  const report = current?.report ?? null;
  const error = current?.error ?? "";

  useEffect(() => {
    let live = true;
    getCommissionReport(month).then(
      (loaded) => { if (live) setResult({ month, report: loaded }); },
      (err: unknown) => { if (live) setResult({ month, error: message(err, "Could not load the commission report.") }); },
    );
    return () => { live = false; };
  }, [month, reloads]);
  useEffect(() => {
    if (canAssign) listSalesStaffOptions().then(setColleagues).catch(() => setColleagues([]));
  }, [canAssign]);

  const label = months.find((item) => item.value === month)?.label ?? month;
  const all = report ? [...report.rows, report.unattributed] : [];
  const selected = all.find((row) => rowKey(row) === openKey);
  const unattributed = report?.unattributed;

  async function assign(invoiceId: string, invoiceNumber: string, staffId: string) {
    setAssignError("");
    try {
      await updateInvoiceSalesStaff(invoiceId, staffId);
      setNotice(`${invoiceNumber} now counts for ${colleagues.find((item) => item.id === staffId)?.name ?? "the colleague"}.`);
      setReloads((count) => count + 1);
    } catch (err) {
      setAssignError(message(err, "Could not assign the invoice."));
    }
  }

  return (
    <Stack gap={6}>
      <div className="firstout-page-header">
        <div>
          <h1 className="cds--type-productive-heading-04">Commission</h1>
          <p className="cds--type-body-01">Commission per colleague for the month. Use it at month end to pay commission.</p>
        </div>
        <Button
          kind="ghost"
          renderIcon={Download}
          disabled={!report}
          onClick={() => report && downloadCsv(`commission-${report.month}.csv`, COMMISSION_CSV_HEADERS, commissionCsvRows(report))}
        >
          Export CSV
        </Button>
      </div>
      <div style={{ maxWidth: "15rem" }}>
        <Select id="commission-month" labelText="Month" value={month} onChange={(event) => { setMonth(event.target.value); setOpenKey(null); }}>
          {months.map((item) => <SelectItem key={item.value} value={item.value} text={item.label} />)}
        </Select>
      </div>
      {notice && <InlineNotification lowContrast kind="success" title={notice} onCloseButtonClick={() => setNotice("")} />}
      {error ? (
        <Stack gap={3}>
          <InlineNotification lowContrast kind="error" title="Commission report unavailable" subtitle={error} hideCloseButton />
          <div><Button kind="tertiary" size="sm" onClick={() => setReloads((count) => count + 1)}>Retry</Button></div>
        </Stack>
      ) : !report ? (
        <DataTableSkeleton aria-label="Loading commission" columnCount={8} rowCount={3} showHeader={false} showToolbar={false} />
      ) : (
        <>
          <dl aria-label="Commission summary" className={metrics.metrics}>
            <div className={metrics.metric}>
              <dt>Commissionable sales</dt>
              <dd>{zar(report.rows.reduce((sum, row) => sum + Number(row.net_commissionable), 0))}</dd>
              <dd className={metrics.capacityNote}>Excl. VAT, after credit notes</dd>
            </div>
            <div className={metrics.metric}>
              <dt>Commission payable</dt>
              <dd>{zar(report.commission)}</dd>
              <dd className={metrics.capacityNote}>Excluded lines (such as delivery): {zar(report.excluded_ex_vat)}</dd>
            </div>
            <div className={metrics.metric}>
              <dt>Unattributed sales</dt>
              <dd>{zar(unattributed?.commissionable_ex_vat ?? 0)}</dd>
              <dd className={metrics.capacityNote}>
                {unattributed?.invoice_count
                  ? `${unattributed.invoice_count} ${unattributed.invoice_count === 1 ? "invoice" : "invoices"} without a colleague`
                  : "Every sale has a colleague"}
              </dd>
            </div>
          </dl>
          <div role="region" aria-label="Commission by colleague" tabIndex={0} style={{ overflowX: "auto" }}>
            <Table size="md" aria-label={`Commission for ${label}`}>
              <TableHead>
                <TableRow>
                  <TableHeader>Colleague</TableHeader>
                  <TableHeader>Invoices</TableHeader>
                  <TableHeader>Commissionable excl. VAT</TableHeader>
                  <TableHeader>Excluded excl. VAT</TableHeader>
                  <TableHeader>Credit notes</TableHeader>
                  <TableHeader>Net</TableHeader>
                  <TableHeader>Rate</TableHeader>
                  <TableHeader>Commission</TableHeader>
                  <TableHeader><span className="cds--visually-hidden">Actions</span></TableHeader>
                </TableRow>
              </TableHead>
              <TableBody>
                {all.map((row) => {
                  const nobody = row.sales_staff_id === null;
                  return (
                    <TableRow key={rowKey(row)}>
                      <TableCell>
                        <Button kind="ghost" size="sm" onClick={() => setOpenKey(rowKey(row))}>
                          {row.name}{!nobody && !row.is_active ? " (inactive)" : ""}
                        </Button>
                      </TableCell>
                      <TableCell>{row.invoice_count}</TableCell>
                      <TableCell>{zar(row.commissionable_ex_vat)}</TableCell>
                      <TableCell>{zar(row.excluded_ex_vat)}</TableCell>
                      <TableCell>{zar(-Number(row.credit_deductions))}</TableCell>
                      <TableCell>{zar(row.net_commissionable)}</TableCell>
                      <TableCell>{nobody ? "—" : `${Number(row.commission_rate)}%`}</TableCell>
                      <TableCell>{nobody ? "—" : zar(row.commission)}</TableCell>
                      <TableCell>
                        {nobody && canAssign && row.invoice_count > 0 ? (
                          <Button kind="ghost" size="sm" onClick={() => setOpenKey(rowKey(row))}>Assign</Button>
                        ) : null}
                      </TableCell>
                    </TableRow>
                  );
                })}
                <TableRow>
                  <TableCell><strong>Total</strong></TableCell>
                  <TableCell>{report.invoice_count}</TableCell>
                  <TableCell>{zar(report.commissionable_ex_vat)}</TableCell>
                  <TableCell>{zar(report.excluded_ex_vat)}</TableCell>
                  <TableCell>{zar(-Number(report.credit_deductions))}</TableCell>
                  <TableCell>{zar(report.net_commissionable)}</TableCell>
                  <TableCell />
                  <TableCell><strong>{zar(report.commission)}</strong></TableCell>
                  <TableCell />
                </TableRow>
              </TableBody>
            </Table>
          </div>
          <p className="cds--type-helper-text-01">
            Imported invoices aren&apos;t counted. Select a colleague to check their invoices.
          </p>
        </>
      )}
      {selected && (
        <Modal
          open
          passiveModal
          size="md"
          modalHeading={selected.name}
          modalLabel={`${label} · ${selected.invoice_count} ${selected.invoice_count === 1 ? "invoice" : "invoices"}`}
          onRequestClose={() => { setOpenKey(null); setAssignError(""); }}
        >
          <Stack gap={5}>
            {selected.sales_staff_id === null && (
              <p>These invoices have no colleague. Assign each one so it counts for commission.</p>
            )}
            {assignError && <InlineNotification lowContrast kind="error" title="Not assigned" subtitle={assignError} hideCloseButton />}
            {selected.documents.length === 0 ? (
              <p>No invoices this month.</p>
            ) : (
              <Table size="sm" aria-label={`Documents for ${selected.name}`}>
                <TableHead>
                  <TableRow>
                    <TableHeader>Document</TableHeader>
                    <TableHeader>Customer</TableHeader>
                    <TableHeader>Commissionable</TableHeader>
                    <TableHeader>Excluded</TableHeader>
                    {selected.sales_staff_id === null && canAssign && <TableHeader>Assign to</TableHeader>}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {selected.documents.map((doc) => {
                    const credit = doc.kind === "credit_note";
                    const sign = (value: string) => zar(credit ? -Number(value) : value);
                    return (
                      <TableRow key={doc.kind + doc.id}>
                        <TableCell>
                          <Link href={`/invoices/${doc.invoice_id}`}>{doc.number}</Link>
                          {credit && <small> credits {doc.invoice_number}</small>}
                        </TableCell>
                        <TableCell>{doc.customer_name}</TableCell>
                        <TableCell>{sign(doc.commissionable_ex_vat)}</TableCell>
                        <TableCell>{sign(doc.excluded_ex_vat)}</TableCell>
                        {selected.sales_staff_id === null && canAssign && (
                          <TableCell>
                            {credit ? null : (
                              <Select
                                id={`assign-${doc.id}`}
                                labelText={`Assign ${doc.number} to`}
                                hideLabel
                                size="sm"
                                value=""
                                onChange={(event) => {
                                  if (event.target.value) void assign(doc.invoice_id, doc.number, event.target.value);
                                }}
                              >
                                <SelectItem value="" text="Choose a colleague" />
                                {colleagues.map((item) => <SelectItem key={item.id} value={item.id} text={item.name} />)}
                              </Select>
                            )}
                          </TableCell>
                        )}
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            )}
            <div className="cds--type-body-01">
              <div>Commissionable excl. VAT: {zar(selected.commissionable_ex_vat)}</div>
              <div>Credit notes: {zar(-Number(selected.credit_deductions))}</div>
              <div>Net: {zar(selected.net_commissionable)}</div>
              {selected.sales_staff_id !== null && (
                <div><strong>Commission at {Number(selected.commission_rate)}%: {zar(selected.commission)}</strong></div>
              )}
            </div>
          </Stack>
        </Modal>
      )}
    </Stack>
  );
}

export default function CommissionPage() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user || !(can(user, "books.mutate") || can(user, "users.manage"))) {
    return <InlineNotification kind="error" title="Access denied" subtitle="Books or staff management permission is required." hideCloseButton />;
  }
  return <CommissionScreen canAssign={can(user, "books.mutate")} />;
}

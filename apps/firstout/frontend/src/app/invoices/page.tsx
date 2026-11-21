"use client";

import { Button, InlineNotification, Stack, Tag } from "@carbon/react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { ArchiveInvoiceModal } from "@/components/archive-invoice-modal";
import { KpiStrip } from "@/components/kpi-strip";
import {
  RecordDetail,
  RecordDetails,
  RecordWorkspace,
  type RecordWorkspaceAdapter,
} from "@/components/record-workspace";
import {
  canMutateBooks,
  downloadInvoicePdf,
  formatZarAmount,
  getInvoiceSummary,
  invoiceAction,
  listSalesStaffOptions,
  type InvoiceListItem,
  type InvoiceSource,
  type InvoiceSummary,
  type SalesStaffOption,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { invoiceStatusTag } from "@/lib/payment-status";
import { workspaceIdentity } from "@/lib/record-workspace";
import { formatSettlementAmount } from "@/lib/source-history";

const SOURCES: Record<InvoiceSource, { label: string; tag: "blue" | "teal" | "warm-gray" }> = {
  till: { label: "Till", tag: "blue" },
  manual: { label: "Manual", tag: "teal" },
  imported: { label: "Imported", tag: "warm-gray" },
};

const STATUS_FILTER = [
  { value: "paid", label: "Paid" },
  { value: "partially_paid", label: "Partly paid" },
  { value: "unpaid", label: "Unpaid" },
  { value: "on_statement", label: "On statement" },
  { value: "overdue", label: "Overdue" },
] as const;

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

function StatusTag({ invoice }: { invoice: InvoiceListItem }) {
  const status = invoiceStatusTag(invoice);
  return <Tag type={status.type} size="sm">{status.label}</Tag>;
}

function SourceTag({ invoice }: { invoice: InvoiceListItem }) {
  const source = SOURCES[invoice.source];
  return <Tag type={source.tag} size="sm">{source.label}</Tag>;
}

function invoicesAdapter(colleagues: readonly SalesStaffOption[]) {
  const settled = (item: InvoiceListItem, value: string) => formatSettlementAmount(value, item.is_archive);
  return {
    resource: "invoices",
    title: "Invoices",
    singular: "invoice",
    breadcrumb: "Books",
    description: "Tax invoices with 15% VAT.",
    defaultSort: "-issue_date",
    columns: [
      { key: "invoice_number", label: "Number", sortable: true, render: (item) => item.invoice_number },
      { key: "customer_name", label: "Customer", sortable: true, render: (item) => item.customer_name },
      { key: "issue_date", label: "Issue date", sortable: true, render: (item) => item.issue_date },
      { key: "due_date", label: "Due date", sortable: true, render: (item) => item.due_date ?? "—" },
      {
        key: "sales_staff_name",
        label: "Sales colleague",
        sortable: true,
        render: (item) => item.sales_staff_name ?? "—",
      },
      {
        key: "subtotal_ex_vat",
        label: "Ex VAT",
        numeric: true,
        sortable: true,
        render: (item) => formatZarAmount(item.subtotal_ex_vat),
      },
      { key: "vat_amount", label: "VAT", numeric: true, render: (item) => formatZarAmount(item.vat_amount) },
      {
        key: "total_inc_vat",
        label: "Total",
        numeric: true,
        sortable: true,
        render: (item) => formatZarAmount(item.total_inc_vat),
      },
      { key: "amount_paid", label: "Paid", numeric: true, render: (item) => settled(item, item.amount_paid) },
      {
        key: "balance",
        label: "Balance owing",
        numeric: true,
        sortable: true,
        render: (item) => settled(item, item.balance),
      },
      { key: "status", label: "Status", sortable: true, render: (item) => <StatusTag invoice={item} /> },
      { key: "source", label: "Source", sortable: true, render: (item) => <SourceTag invoice={item} /> },
    ],
    filters: [
      { key: "status", label: "Status", type: "enum", quick: true, allLabel: "All statuses", options: STATUS_FILTER },
      {
        key: "sales_staff_id",
        label: "Sales colleague",
        type: "enum",
        quick: true,
        allLabel: "All colleagues",
        options: colleagues.map((item) => ({ value: item.id, label: item.name })),
      },
      {
        key: "source",
        label: "Source",
        type: "enum",
        options: (Object.keys(SOURCES) as InvoiceSource[]).map((value) => ({ value, label: SOURCES[value].label })),
      },
      { key: "customer_name", label: "Customer", type: "text" },
      { key: "issue_date", label: "Issue date", type: "date" },
      { key: "due_date", label: "Due date", type: "date" },
      { key: "total_inc_vat", label: "Total", type: "number" },
      { key: "balance", label: "Balance owing", type: "number" },
    ],
    actions: [
      { key: "archive", label: "Archive" },
      { key: "restore", label: "Restore" },
    ],
    lifecycle: { activeLabel: "Active", archivedLabel: "Archived" },
    getTitle: (item) => item.invoice_number,
    getSubtitle: (item) => [item.customer_name, item.issue_date].join(" · "),
  } satisfies RecordWorkspaceAdapter<InvoiceListItem>;
}

export default function InvoicesPage() {
  const { user } = useAuth();
  return <InvoicesContent key={workspaceIdentity(user)} />;
}

function InvoicesContent() {
  const router = useRouter();
  const { user } = useAuth();
  const canMutate = canMutateBooks(user);
  const [colleagues, setColleagues] = useState<SalesStaffOption[]>([]);
  const [summary, setSummary] = useState<InvoiceSummary | null | undefined>();
  const [refreshKey, setRefreshKey] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [archiving, setArchiving] = useState<InvoiceListItem | null>(null);
  const adapter = useMemo(() => invoicesAdapter(colleagues), [colleagues]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    getInvoiceSummary()
      .then((totals) => { if (!cancelled) setSummary(totals); })
      .catch((err: unknown) => {
        if (cancelled) return;
        setSummary(null);
        setError(err instanceof Error ? err.message : "Failed to load invoice totals.");
      });
    return () => { cancelled = true; };
  }, [user, refreshKey]);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    // Keep the adapter stable after the first load; the filter still works without names.
    listSalesStaffOptions()
      .then((rows) => { if (!cancelled) setColleagues(rows); })
      .catch(() => undefined);
    return () => { cancelled = true; };
  }, [user]);

  async function run(label: string, action: () => Promise<string>) {
    setBusy(true);
    setError(null);
    try {
      setNotice(await action());
      setRefreshKey((value) => value + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${label}.`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Stack gap={6}>
      {error ? (
        <InlineNotification kind="error" title="Error" subtitle={error} onCloseButtonClick={() => setError(null)} lowContrast />
      ) : null}
      {notice ? (
        <InlineNotification kind="success" title="Done" subtitle={notice} onCloseButtonClick={() => setNotice(null)} lowContrast />
      ) : null}

      <RecordWorkspace<InvoiceListItem>
        adapter={adapter}
        refreshKey={refreshKey}
        onCreate={canMutate ? () => router.push("/invoices/new") : undefined}
        createLabel="Create invoice"
        summary={
          <KpiStrip
            label="Invoice totals"
            count={4}
            items={
              summary && [
                {
                  label: "Outstanding",
                  value: formatZarAmount(summary.outstanding_zar),
                  sub: `${plural(summary.outstanding_count, "invoice")} with a balance`,
                },
                {
                  label: "Overdue",
                  value: formatZarAmount(summary.overdue_zar),
                  sub: `${plural(summary.overdue_count, "invoice")} past the due date`,
                  warn: summary.overdue_count > 0,
                },
                {
                  label: "On statement",
                  value: formatZarAmount(summary.on_statement_zar),
                  sub: `${plural(summary.on_statement_count, "invoice")} on account`,
                },
                {
                  label: "Paid this month",
                  value: formatZarAmount(summary.paid_this_month_zar),
                  sub: plural(summary.paid_this_month_count, "payment"),
                },
              ]
            }
          />
        }
        renderDetails={(item, { archived }) => {
          const live = !item.is_archive;
          return (
            <Stack gap={5}>
              <RecordDetails>
                <RecordDetail label="Customer">{item.customer_name}</RecordDetail>
                <RecordDetail label="Issue date">{item.issue_date}</RecordDetail>
                <RecordDetail label="Due date">{item.due_date}</RecordDetail>
                <RecordDetail label="Sales colleague">{item.sales_staff_name}</RecordDetail>
                <RecordDetail label="Total">{formatZarAmount(item.total_inc_vat)}</RecordDetail>
                <RecordDetail label="Balance owing">{formatSettlementAmount(item.balance, item.is_archive)}</RecordDetail>
                <RecordDetail label="Status"><StatusTag invoice={item} /></RecordDetail>
                <RecordDetail label="Source"><SourceTag invoice={item} /></RecordDetail>
              </RecordDetails>
              <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
                <Button kind="tertiary" size="sm" href={`/invoices/${item.id}`}>
                  Open
                </Button>
                {live ? (
                  <Button
                    kind="ghost"
                    size="sm"
                    disabled={busy}
                    onClick={() => void run("download the tax invoice", async () => {
                      await downloadInvoicePdf(item.id, item.invoice_number);
                      return `${item.invoice_number}.pdf downloaded.`;
                    })}
                  >
                    Download
                  </Button>
                ) : null}
                {canMutate && live && Number(item.balance) > 0 ? (
                  <Button kind="primary" size="sm" href={`/invoices/${item.id}?action=pay`}>
                    Record payment
                  </Button>
                ) : null}
                {canMutate && live ? (
                  <Button kind="ghost" size="sm" href={`/invoices/${item.id}?action=credit`}>
                    Issue credit note
                  </Button>
                ) : null}
                {canMutate && live ? (
                  archived ? (
                    <Button
                      kind="ghost"
                      size="sm"
                      disabled={busy}
                      onClick={() => void run("restore the invoice", async () => {
                        await invoiceAction(item.id, "restore");
                        return `${item.invoice_number} restored. It's back in the active list.`;
                      })}
                    >
                      Restore
                    </Button>
                  ) : (
                    <Button kind="ghost" size="sm" disabled={busy} onClick={() => setArchiving(item)}>
                      Archive
                    </Button>
                  )
                ) : null}
              </div>
            </Stack>
          );
        }}
      />

      <ArchiveInvoiceModal
        invoiceNumber={archiving?.invoice_number ?? null}
        onClose={() => setArchiving(null)}
        onConfirm={() => {
          const invoice = archiving;
          setArchiving(null);
          if (!invoice) return;
          void run("archive the invoice", async () => {
            await invoiceAction(invoice.id, "archive");
            return `${invoice.invoice_number} archived. Find it under Archived; it still counts in the books, VAT and reports.`;
          });
        }}
      />
    </Stack>
  );
}

"use client";

import { Button, InlineNotification, Stack, Tag } from "@carbon/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { BillPaymentModal } from "@/components/bill-payment-modal";
import { KpiStrip } from "@/components/kpi-strip";
import {
  RecordDetail,
  RecordDetails,
  RecordWorkspace,
  type RecordWorkspaceAdapter,
} from "@/components/record-workspace";
import {
  billAction,
  canMutateBooks,
  formatZarAmount,
  getBillSummary,
  listSuppliers,
  type BillListItem,
  type BillSummary,
  type Supplier,
} from "@/lib/api";
import { usePageError } from "@/hooks/use-page-error";
import { useAuth } from "@/lib/auth";
import { BILL_STATUS } from "@/lib/payment-status";
import { workspaceIdentity } from "@/lib/record-workspace";

function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? "" : "s"}`;
}

function BillStatusTag({ bill }: { bill: BillListItem }) {
  const status = BILL_STATUS[bill.status];
  return <Tag type={status.tag} size="sm">{status.label}</Tag>;
}

function payable(bill: BillListItem): boolean {
  return bill.approval_status === "approved" && !bill.is_archived && Number(bill.balance_foreign) > 0;
}

function billsAdapter(suppliers: readonly Supplier[]) {
  const currencies = [...new Set(["ZAR", ...suppliers.map((supplier) => supplier.default_currency)])].sort();
  return {
    resource: "bills",
    title: "Bills",
    singular: "bill",
    breadcrumb: "Books",
    description: "Supplier bills in foreign currency with ZAR conversion.",
    defaultSort: "due_date",
    columns: [
      { key: "bill_number", label: "Number", sortable: true, render: (item) => item.bill_number },
      { key: "supplier_name", label: "Supplier", sortable: true, render: (item) => item.supplier_name },
      { key: "supplier_ref", label: "Supplier ref", sortable: true, render: (item) => item.supplier_ref || "—" },
      { key: "issue_date", label: "Issue date", sortable: true, render: (item) => item.issue_date },
      { key: "due_date", label: "Due date", sortable: true, render: (item) => item.due_date ?? "—" },
      { key: "currency", label: "Currency", render: (item) => item.currency },
      {
        key: "amount_foreign",
        label: "Amount",
        numeric: true,
        sortable: true,
        render: (item) => `${item.currency} ${item.amount_foreign}`,
      },
      { key: "amount_zar", label: "ZAR", numeric: true, sortable: true, render: (item) => formatZarAmount(item.amount_zar) },
      {
        key: "balance_zar",
        label: "Balance owing",
        numeric: true,
        sortable: true,
        render: (item) => formatZarAmount(item.balance_zar),
      },
      { key: "status", label: "Status", sortable: true, render: (item) => <BillStatusTag bill={item} /> },
      {
        key: "attachment_count",
        label: "Attachments",
        numeric: true,
        render: (item) => (item.attachment_count ? String(item.attachment_count) : "—"),
      },
    ],
    filters: [
      {
        key: "status",
        label: "Status",
        type: "enum",
        quick: true,
        allLabel: "All statuses",
        options: (["draft", "awaiting_approval", "unpaid", "partially_paid", "overdue", "paid"] as const).map(
          (value) => ({ value, label: BILL_STATUS[value].label }),
        ),
      },
      {
        key: "supplier_id",
        label: "Supplier",
        type: "enum",
        quick: true,
        allLabel: "All suppliers",
        options: suppliers.map((supplier) => ({ value: supplier.id, label: supplier.name })),
      },
      {
        key: "currency",
        label: "Currency",
        type: "enum",
        quick: true,
        allLabel: "All currencies",
        options: currencies.map((value) => ({ value, label: value })),
      },
      { key: "supplier_ref", label: "Supplier ref", type: "text" },
      { key: "issue_date", label: "Issue date", type: "date" },
      { key: "due_date", label: "Due date", type: "date" },
      { key: "balance_zar", label: "Balance owing", type: "number" },
    ],
    actions: [
      { key: "archive", label: "Archive" },
      { key: "restore", label: "Restore" },
    ],
    getTitle: (item) => item.bill_number,
    getSubtitle: (item) => [item.supplier_name, item.supplier_ref].filter(Boolean).join(" · "),
  } satisfies RecordWorkspaceAdapter<BillListItem>;
}

export default function BillsPage() {
  const { user } = useAuth();
  return <BillsContent key={workspaceIdentity(user)} />;
}

function BillsContent() {
  const router = useRouter();
  const { user } = useAuth();
  const canMutate = canMutateBooks(user);
  const [refreshKey, setRefreshKey] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [paying, setPaying] = useState<BillListItem | null>(null);
  const client = useQueryClient();
  const summaryQuery = useQuery({ queryKey: ["bill-summary"], queryFn: getBillSummary, enabled: Boolean(user) });
  const suppliersQuery = useQuery({
    queryKey: ["suppliers", "with-archived"],
    // Archived suppliers still have bills to filter by.
    queryFn: async () => {
      const [active, archived] = await Promise.all([listSuppliers(), listSuppliers({ archived: true })]);
      return [...active, ...archived].sort((a, b) => a.name.localeCompare(b.name));
    },
    enabled: Boolean(user),
    // Keep the adapter stable after the first load.
    staleTime: Infinity,
  });
  const suppliers = useMemo(() => suppliersQuery.data ?? [], [suppliersQuery.data]);
  const loadFailure = summaryQuery.error ?? suppliersQuery.error;
  const summary: BillSummary | null | undefined = loadFailure ? null : summaryQuery.data;
  const { error, setError } = usePageError(loadFailure, "Failed to load bill totals.");
  const adapter = useMemo(() => billsAdapter(suppliers), [suppliers]);

  function changed(message: string) {
    setNotice(message);
    setRefreshKey((value) => value + 1);
    void client.invalidateQueries({ queryKey: ["bill-summary"] });
  }

  async function approve(bill: BillListItem) {
    setBusy(true);
    setError(null);
    try {
      await billAction(bill.id, "approve");
      changed(`${bill.bill_number} approved and posted. It's ready to pay.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to approve bill.");
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

      <RecordWorkspace<BillListItem>
        adapter={adapter}
        refreshKey={refreshKey}
        onCreate={canMutate ? () => router.push("/bills/new") : undefined}
        createLabel="Create bill"
        summary={
          <KpiStrip
            label="Bill totals"
            count={4}
            items={
              summary && [
                {
                  label: "Owing (ZAR)",
                  value: formatZarAmount(summary.owing_zar),
                  sub: "Approved and awaiting approval",
                },
                {
                  label: "Overdue",
                  value: formatZarAmount(summary.overdue_zar),
                  sub: plural(summary.overdue_count, "bill"),
                  warn: summary.overdue_count > 0,
                },
                {
                  label: "Due in 7 days",
                  value: formatZarAmount(summary.due_soon_zar),
                  sub: plural(summary.due_soon_count, "bill"),
                },
                {
                  label: "Awaiting approval",
                  value: String(summary.awaiting_approval_count),
                  sub: `${plural(summary.draft_count, "draft")} not yet submitted`,
                },
              ]
            }
          />
        }
        renderDetails={(item, { archived }) => (
          <Stack gap={5}>
            <RecordDetails>
              <RecordDetail label="Supplier">{item.supplier_name}</RecordDetail>
              <RecordDetail label="Supplier ref">{item.supplier_ref}</RecordDetail>
              <RecordDetail label="Issue date">{item.issue_date}</RecordDetail>
              <RecordDetail label="Due date">{item.due_date}</RecordDetail>
              <RecordDetail label="Amount">
                {item.currency} {item.amount_foreign}
                {item.currency !== "ZAR" ? ` (${formatZarAmount(item.amount_zar)} at ${item.fx_to_zar})` : ""}
              </RecordDetail>
              <RecordDetail label="Balance owing">
                {item.currency !== "ZAR" ? `${item.currency} ${item.balance_foreign} · ` : ""}
                {formatZarAmount(item.balance_zar)}
              </RecordDetail>
              <RecordDetail label="Status"><BillStatusTag bill={item} /></RecordDetail>
              <RecordDetail label="Attachments">{item.attachment_count || null}</RecordDetail>
            </RecordDetails>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
              <Button kind="tertiary" size="sm" href={`/bills/${item.id}`}>
                Open
              </Button>
              {canMutate && !archived && item.approval_status !== "approved" ? (
                <Button kind="primary" size="sm" disabled={busy} onClick={() => void approve(item)}>
                  Approve
                </Button>
              ) : null}
              {canMutate && payable(item) ? (
                <Button kind="primary" size="sm" onClick={() => setPaying(item)}>
                  Record payment
                </Button>
              ) : null}
              {canMutate ? (
                <Button kind="ghost" size="sm" href={`/bills/new?from=${item.id}`}>
                  Duplicate
                </Button>
              ) : null}
            </div>
          </Stack>
        )}
      >
        <p className="cds--type-body-01">
          Imported records are available in <Link className="cds--link" href="/history">Searchable history</Link>.
        </p>
      </RecordWorkspace>

      {paying ? (
        <BillPaymentModal
          bill={paying}
          onClose={() => setPaying(null)}
          onRecorded={(payment) => {
            setPaying(null);
            changed(`Payment ${payment.payment_number} recorded against ${paying.bill_number}.`);
          }}
        />
      ) : null}
    </Stack>
  );
}

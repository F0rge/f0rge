"use client";

import { Button, InlineNotification, Stack, Tag } from "@carbon/react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import {
  RecordDetail,
  RecordDetails,
  RecordWorkspace,
  type RecordWorkspaceAdapter,
} from "@/components/record-workspace";
import {
  canMutateQuotes,
  canUseTill,
  downloadQuotePdf,
  duplicateQuote,
  formatZarAmount,
  type QuoteListItem,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { referenceQueries } from "@/lib/queries";
import { QUOTE_STATES, isQuoteOpen, quoteStateInfo } from "@/lib/quote-state";
import { workspaceIdentity } from "@/lib/record-workspace";

export default function QuotesPage() {
  const { user } = useAuth();
  return <QuotesContent key={workspaceIdentity(user)} />;
}

function QuotesContent() {
  const router = useRouter();
  const { user } = useAuth();
  const canMutate = canMutateQuotes(user);
  const canSell = canUseTill(user);
  // ponytail: the filter lists active colleagues; past ones still show in the column.
  const colleagues = useQuery(referenceQueries.salesStaffOptions).data ?? [];
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(action: () => Promise<void>, failure: string) {
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : failure);
    } finally {
      setBusy(false);
    }
  }

  const adapter = {
    resource: "quotes",
    title: "Quotes",
    singular: "quote",
    breadcrumb: "Sell",
    description: "Quotes you can edit, print, and open in the till.",
    defaultSort: "created_at",
    lifecycle: { activeLabel: "Open", archivedLabel: "Converted" },
    columns: [
      { key: "quote_number", label: "Reference", sortable: true, render: (item) => item.quote_number },
      { key: "customer_name", label: "Customer", sortable: true, render: (item) => item.customer_name },
      { key: "issue_date", label: "Issue date", sortable: true, render: (item) => item.issue_date },
      { key: "valid_until", label: "Valid until", sortable: true, render: (item) => item.valid_until ?? "—" },
      { key: "sales_staff_name", label: "Sales colleague", sortable: true, render: (item) => item.sales_staff_name ?? "—" },
      { key: "item_count", label: "Items", numeric: true, sortable: true, render: (item) => item.item_count },
      {
        key: "total_inc_vat", label: "Total", numeric: true, sortable: true,
        render: (item) => formatZarAmount(item.total_inc_vat),
      },
      {
        key: "state", label: "Status",
        render: (item) => {
          const state = quoteStateInfo(item.state);
          return <Tag size="sm" type={state.tag}>{state.label}</Tag>;
        },
      },
    ],
    filters: [
      {
        key: "state", label: "Status", type: "enum", quick: true, allLabel: "All statuses",
        options: QUOTE_STATES.map(({ value, label }) => ({ value, label })),
      },
      {
        key: "sales_staff_id", label: "Sales colleague", type: "enum", quick: true, allLabel: "All colleagues",
        options: colleagues.map((item) => ({ value: item.id, label: item.name })),
      },
      { key: "customer_name", label: "Customer", type: "text" },
      { key: "issue_date", label: "Issue date", type: "date" },
      { key: "valid_until", label: "Valid until", type: "date" },
      { key: "total_inc_vat", label: "Total", type: "number" },
    ],
    actions: canMutate ? [{ key: "delete", label: "Delete", danger: true }] : [],
    getTitle: (item) => item.quote_number,
    getSubtitle: (item) => item.customer_name,
    canEdit: (item) => canMutate && isQuoteOpen(item),
  } satisfies RecordWorkspaceAdapter<QuoteListItem>;

  return (
    <Stack gap={6}>
      {error ? (
        <InlineNotification
          kind="error"
          title="Error"
          subtitle={error}
          onCloseButtonClick={() => setError(null)}
          lowContrast
        />
      ) : null}
      <RecordWorkspace<QuoteListItem>
        adapter={adapter}
        onCreate={canMutate ? () => router.push("/quotes/new") : undefined}
        createLabel="New quote"
        onEdit={(item) => router.push(`/quotes/${item.id}`)}
        renderDetails={(item) => {
          const state = quoteStateInfo(item.state);
          return (
            <Stack gap={5}>
              <RecordDetails>
                <RecordDetail label="Status"><Tag size="sm" type={state.tag}>{state.label}</Tag></RecordDetail>
                <RecordDetail label="Customer">{item.customer_name}</RecordDetail>
                <RecordDetail label="Issue date">{item.issue_date}</RecordDetail>
                <RecordDetail label="Valid until">{item.valid_until ?? "—"}</RecordDetail>
                <RecordDetail label="Sales colleague">{item.sales_staff_name ?? "—"}</RecordDetail>
                <RecordDetail label="Items">{item.items_label}</RecordDetail>
                <RecordDetail label="Total incl. VAT">{formatZarAmount(item.total_inc_vat)}</RecordDetail>
                {item.converted_invoice_id && (
                  <RecordDetail label="Invoice">
                    <a href={`/invoices/${item.converted_invoice_id}`}>
                      {item.converted_invoice_number ?? "Open invoice"}
                    </a>
                  </RecordDetail>
                )}
              </RecordDetails>
              <Stack gap={3} orientation="horizontal">
                {!isQuoteOpen(item) && (
                  <Button kind="tertiary" size="sm" onClick={() => router.push(`/quotes/${item.id}`)}>
                    View
                  </Button>
                )}
                {canSell && isQuoteOpen(item) && (
                  <Button kind="tertiary" size="sm" onClick={() => router.push(`/till?quote=${item.id}`)}>
                    Open in till
                  </Button>
                )}
                <Button
                  kind="ghost"
                  size="sm"
                  disabled={busy}
                  onClick={() => void run(() => downloadQuotePdf(item.id, item.quote_number), "Could not download the quote.")}
                >
                  Download PDF
                </Button>
                {canMutate && (
                  <Button
                    kind="ghost"
                    size="sm"
                    disabled={busy}
                    onClick={() => void run(async () => {
                      const copy = await duplicateQuote(item.id);
                      router.push(`/quotes/${copy.id}`);
                    }, "Could not duplicate the quote.")}
                  >
                    Duplicate
                  </Button>
                )}
              </Stack>
            </Stack>
          );
        }}
      />
    </Stack>
  );
}

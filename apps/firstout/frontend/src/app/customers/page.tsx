"use client";

import {
  Button,
  InlineNotification,
  Modal,
  Stack,
  Tab,
  TabList,
  TabPanel,
  TabPanels,
  Tabs,
  Tag,
} from "@carbon/react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { CustomerCrmBadges } from "@/components/customer-crm-badges";
import {
  CustomerDuplicateModal,
  DUPLICATE_NAME_TAKEN,
} from "@/components/customer-duplicate-modal";
import {
  CustomerFormFields,
  RepriceDraftsModal,
  customerWritePayload,
  emptyCustomerForm,
  formFromCustomer,
} from "@/components/customer-form-fields";
import { CustomerPortalAccessPanel } from "@/components/customer-portal-access";
import {
  RecordDetail,
  RecordDetails,
  RecordWorkspace,
  type RecordWorkspaceAdapter,
  type WorkspaceField,
} from "@/components/record-workspace";
import { SalesHistoryTable } from "@/components/records/history-tables";
import { PartyRecords } from "@/components/records/party-records";
import {
  ApiError,
  PRICE_CLASSIFICATIONS,
  canManageCustomerCredit,
  canMutateCustomers,
  customerInvoicesHref,
  createCustomer,
  findCustomerDuplicates,
  formatZarAmount,
  repriceCustomerDrafts,
  updateCustomer,
  type CreateCustomerPayload,
  type CustomerCrm,
  type CustomerDuplicateMatch,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { workspaceIdentity } from "@/lib/record-workspace";
import {
  formatIsoDate,
  laybyActiveBadgeLabel,
  overdueBadgeLabel,
} from "@/lib/customer-crm";
import { downloadCsv } from "@/lib/csv";
import {
  queryWorkspace,
  type WorkspaceQuery,
} from "@/lib/record-workspace-api";

const classificationOptions = PRICE_CLASSIFICATIONS.map((value) => ({
  value,
  label: value,
}));
const currency = (value: string | null | undefined) =>
  value == null ? "—" : formatZarAmount(value);

export default function CustomersPage() {
  const { user } = useAuth();
  return <CustomersScreen key={workspaceIdentity(user)} />;
}
function CustomersScreen() {
  const router = useRouter();
  const { user } = useAuth();
  const allowed = canMutateCustomers(user);
  const canEditCredit = canManageCustomerCredit(user);
  const [refreshKey, refresh] = useState(0);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<CustomerCrm | null>(null);
  const [form, setForm] = useState<CreateCustomerPayload>(emptyCustomerForm);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [duplicateOpen, setDuplicateOpen] = useState(false);
  const [duplicates, setDuplicates] = useState<CustomerDuplicateMatch[]>([]);
  const [duplicateError, setDuplicateError] = useState<string | null>(null);
  const [reprice, setReprice] = useState<CustomerCrm | null>(null);
  const [repriceBusy, setRepriceBusy] = useState(false);
  const [portal, setPortal] = useState<CustomerCrm | null>(null);
  const closeDuplicates = () => {
    setDuplicateOpen(false);
    setDuplicates([]);
    setDuplicateError(null);
  };
  const start = (item?: CustomerCrm) => {
    setError(null);
    setEditing(item ?? null);
    setForm(item ? formFromCustomer(item) : { ...emptyCustomerForm });
    setCreating(!item);
  };
  const close = () => {
    setCreating(false);
    setEditing(null);
    closeDuplicates();
  };
  async function save(force = false) {
    if (!form.name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const payload = customerWritePayload(form, canEditCredit);
      if (editing) {
        const previousClassification = editing.price_classification;
        const updated = await updateCustomer(editing.id, payload);
        close();
        refresh((value) => value + 1);
        if (
          previousClassification !== updated.price_classification &&
          (updated.draft_quote_count ?? 0) +
            (updated.draft_sales_order_count ?? 0) >
            0
        )
          setReprice(updated);
      } else {
        if (!force) {
          const matches = await findCustomerDuplicates({
            name: form.name.trim(),
            email: form.email,
            phone: form.phone,
          });
          if (matches.length) {
            setDuplicates(matches);
            setDuplicateError(null);
            setDuplicateOpen(true);
            return;
          }
        }
        await createCustomer(payload);
        close();
        setForm({ ...emptyCustomerForm });
        refresh((value) => value + 1);
      }
    } catch (err) {
      if (!editing && err instanceof ApiError && err.status === 409) {
        setDuplicateError(DUPLICATE_NAME_TAKEN);
        setDuplicateOpen(true);
        if (!duplicates.length) {
          try {
            setDuplicates(
              await findCustomerDuplicates({
                name: form.name.trim(),
                email: form.email,
                phone: form.phone,
              }),
            );
          } catch {
            setDuplicates([]);
          }
        }
      } else
        setError(
          err instanceof Error ? err.message : "Could not save customer.",
        );
    } finally {
      setBusy(false);
    }
  }
  async function confirmReprice() {
    if (!reprice) return;
    setRepriceBusy(true);
    setError(null);
    try {
      await repriceCustomerDrafts(reprice.id);
      setReprice(null);
      refresh((value) => value + 1);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not reprice drafts.",
      );
    } finally {
      setRepriceBusy(false);
    }
  }
  async function exportCustomers(query: WorkspaceQuery) {
    const customers: CustomerCrm[] = [];
    for (let offset = 0; offset < 20000; offset += 100) {
      const page = await queryWorkspace<CustomerCrm>("customers", {
        ...query,
        offset,
        limit: 100,
      });
      customers.push(...page.items);
      if (customers.length >= page.total) break;
      if (offset === 19900)
        throw new Error(
          "Refine the filters before exporting more than 20,000 customers.",
        );
    }
    downloadCsv(
      query.lifecycle === "archived"
        ? "firstout-archived-customers.csv"
        : "firstout-customers.csv",
      [
        "Customer",
        "Classification",
        "Cin7 price tier",
        "Email",
        "Phone",
        "Open invoices",
        "Active laybys",
        "Overdue",
        "Layby active",
        "Last purchase",
      ],
      customers.map((item) => [
        item.name,
        item.price_classification,
        item.price_tier,
        item.email ?? "",
        item.phone ?? "",
        item.open_invoices_count > 0 ? currency(item.open_invoices_zar) : "",
        item.active_laybys_count > 0 ? currency(item.active_laybys_zar) : "",
        item.overdue_invoices_count > 0 ? overdueBadgeLabel(item) : "",
        item.active_laybys_count > 0 ? laybyActiveBadgeLabel(item) : "",
        formatIsoDate(item.last_purchase_date),
      ]),
    );
  }
  const bulkFields: WorkspaceField[] = [
    {
      key: "price_classification",
      label: "Classification",
      type: "enum",
      options: classificationOptions,
    },
    {
      key: "payment_terms_days",
      label: "Payment terms (days)",
      type: "number",
      nullable: true,
    },
    ...(canEditCredit
      ? [
          {
            key: "on_hold",
            label: "Account on hold",
            type: "boolean" as const,
          },
          {
            key: "on_hold_reason",
            label: "Hold reason",
            type: "text" as const,
            nullable: true,
          },
          {
            key: "credit_limit",
            label: "Credit limit",
            type: "number" as const,
            nullable: true,
          },
        ]
      : []),
  ];
  const adapter: RecordWorkspaceAdapter<CustomerCrm> = {
    resource: "customers",
    title: "Customers",
    singular: "customer",
    breadcrumb: "Sales",
    description: "Find customers, review balances and manage account details.",
    columns: [
      {
        key: "name",
        label: "Customer / reference",
        render: (item) => item.name,
        sortable: true,
      },
      {
        key: "price_classification",
        label: "Classification",
        render: (item) => (
          <Tag type="gray" size="sm">
            {item.price_classification}
          </Tag>
        ),
        sortable: true,
      },
      {
        key: "open_invoices_zar",
        label: "Open balance",
        render: (item) => (
          <>
            {currency(item.open_invoices_zar)}
            {item.overdue_invoices_count > 0 && (
              <div className="firstout-muted-text">Overdue</div>
            )}
          </>
        ),
        numeric: true,
        sortable: true,
      },
    ],
    filters: [
      { key: "name", label: "Name", type: "text" },
      { key: "email", label: "Email", type: "text" },
      { key: "phone", label: "Phone", type: "text" },
      {
        key: "price_classification",
        label: "Classification",
        type: "enum",
        options: classificationOptions,
        quick: true,
      },
      {
        key: "open_invoices_zar",
        label: "Open balance",
        type: "number",
        quick: true,
      },
      { key: "overdue_invoices_zar", label: "Overdue balance", type: "number" },
      { key: "active_laybys_zar", label: "Active laybys", type: "number" },
      ...(canEditCredit
        ? [
            {
              key: "on_hold",
              label: "Account on hold",
              type: "boolean" as const,
            },
          ]
        : []),
    ],
    bulkFields,
    lifecycle: { activeLabel: "Active", archivedLabel: "Archived" },
    actions: allowed
      ? [
          { key: "edit", label: "Edit" },
          { key: "archive", label: "Archive" },
          { key: "restore", label: "Restore" },
        ]
      : [],
    getTitle: (item) => item.name,
    getSubtitle: (item) => item.email || item.phone || item.price_tier,
    canEdit: (item) => !item.is_archived,
  };
  return (
    <>
      {error && !creating && !editing && (
        <InlineNotification
          kind="error"
          title="Could not complete action"
          subtitle={error}
          onCloseButtonClick={() => setError(null)}
          lowContrast
        />
      )}
      <RecordWorkspace
        adapter={adapter}
        refreshKey={refreshKey}
        onCreate={allowed ? () => start() : undefined}
        onEdit={allowed ? (item) => start(item) : undefined}
        onExport={exportCustomers}
        renderDetails={(item) => (
          <Tabs>
            <TabList aria-label="Customer information">
              <Tab>Overview</Tab>
              <Tab>Records</Tab>
              <Tab>History</Tab>
            </TabList>
            <TabPanels>
              <TabPanel>
                <Stack gap={5}>
                  <CustomerCrmBadges customer={item} />
                  <RecordDetails>
                    <RecordDetail label="Open balance">
                      {currency(item.open_invoices_zar)}
                    </RecordDetail>
                    <RecordDetail label="Overdue">
                      {currency(item.overdue_invoices_zar)}
                    </RecordDetail>
                    <RecordDetail label="Active laybys">
                      {currency(item.active_laybys_zar)}
                    </RecordDetail>
                    <RecordDetail label="Classification">
                      {item.price_classification} ·{" "}
                      {item.price_classification === "Retail"
                        ? "incl. VAT"
                        : "excl. VAT"}
                    </RecordDetail>
                    <RecordDetail label="Price tier">
                      {item.price_tier}
                    </RecordDetail>
                    <RecordDetail label="Email">{item.email}</RecordDetail>
                    <RecordDetail label="Phone">{item.phone}</RecordDetail>
                    <RecordDetail label="VAT number">
                      {item.vat_number}
                    </RecordDetail>
                    <RecordDetail label="Billing address">
                      {item.billing_address}
                    </RecordDetail>
                    <RecordDetail label="Payment terms">
                      {item.payment_terms_days == null
                        ? "Default"
                        : `${item.payment_terms_days} days`}
                    </RecordDetail>
                    {canEditCredit && (
                      <RecordDetail label="Credit limit">
                        {currency(item.credit_limit)}
                      </RecordDetail>
                    )}
                    <RecordDetail label="Last purchase">
                      {formatIsoDate(item.last_purchase_date)}
                    </RecordDetail>
                  </RecordDetails>
                  <div className="firstout-catalogue-actions">
                    <Button
                      kind="ghost"
                      size="sm"
                      href={customerInvoicesHref(item.name)}
                    >
                      View invoices
                    </Button>
                    <Button
                      kind="ghost"
                      size="sm"
                      href={`/laybys?customer=${item.id}`}
                    >
                      View laybys
                    </Button>
                  </div>
                  {allowed &&
                    !item.is_archived &&
                    item.customer_type === "trade" && (
                      <Button kind="tertiary" onClick={() => setPortal(item)}>
                        Manage trade access
                      </Button>
                    )}
                </Stack>
              </TabPanel>
              <TabPanel>
                <PartyRecords key={item.id} kind="customers" id={item.id} />
              </TabPanel>
              <TabPanel>
                <SalesHistoryTable key={item.id} customerId={item.id} />
              </TabPanel>
            </TabPanels>
          </Tabs>
        )}
      />
      <Modal
        open={(creating || editing !== null) && !duplicateOpen}
        modalHeading={editing ? "Edit customer" : "New customer"}
        primaryButtonText={busy ? "Saving…" : "Save customer"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={busy || !form.name.trim()}
        onRequestClose={() => {
          if (!busy) close();
        }}
        onRequestSubmit={() => void save()}
        size="md"
      >
        <Stack gap={5}>
          {error && (
            <InlineNotification
              kind="error"
              title="Could not save"
              subtitle={error}
              hideCloseButton
              lowContrast
            />
          )}
          <CustomerFormFields
            disabled={busy}
            idPrefix={editing ? "edit-customer" : "create-customer"}
            form={form}
            onChange={(patch) =>
              setForm((current) => ({ ...current, ...patch }))
            }
            showCreditFields={canEditCredit}
          />
        </Stack>
      </Modal>
      <CustomerDuplicateModal
        open={duplicateOpen}
        matches={duplicates}
        saving={busy}
        error={duplicateError}
        onCancel={closeDuplicates}
        onCreateAnyway={() => void save(true)}
        onOpenExisting={(id) => {
          close();
          router.push(`/customers/${id}`);
        }}
      />
      <RepriceDraftsModal
        open={reprice !== null}
        quotes={reprice?.draft_quote_count ?? 0}
        orders={reprice?.draft_sales_order_count ?? 0}
        busy={repriceBusy}
        onConfirm={() => void confirmReprice()}
        onCancel={() => setReprice(null)}
      />
      <Modal
        open={portal !== null}
        passiveModal
        modalHeading="Trade portal access"
        size="lg"
        onRequestClose={() => setPortal(null)}
      >
        {portal && (
          <CustomerPortalAccessPanel
            key={portal.id}
            customerId={portal.id}
            defaultEmail={portal.email ?? ""}
          />
        )}
      </Modal>
    </>
  );
}

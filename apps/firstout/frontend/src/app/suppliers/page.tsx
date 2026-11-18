"use client";
import {
  InlineNotification,
  Modal,
  Stack,
  Tab,
  TabList,
  TabPanel,
  TabPanels,
  Tabs,
  TextArea,
  TextInput,
} from "@carbon/react";
import { useEffect, useState } from "react";
import {
  RecordDetail,
  RecordDetails,
  RecordWorkspace,
  type RecordWorkspaceAdapter,
} from "@/components/record-workspace";
import { PartyRecords } from "@/components/records/party-records";
import {
  PurchaseHistoryTable,
  SupplierPricesTable,
} from "@/components/records/history-tables";
import {
  apiFetch,
  canMutateCatalogue,
  createSupplier,
  getSupplierLeadTimes,
  type SupplierLeadTimeRow,
  type CreateSupplierPayload,
  type Supplier,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { workspaceIdentity } from "@/lib/record-workspace";
import {
  formatObservedMedianLine,
  supplierLeadTimeById,
} from "@/lib/lead-times";

const currencies = ["ZAR", "USD", "EUR", "GBP"].map((value) => ({
  value,
  label: value,
}));
export default function SuppliersPage() {
  const { user } = useAuth();
  return <SuppliersScreen key={workspaceIdentity(user)} />;
}
function SuppliersScreen() {
  const { user } = useAuth();
  const allowed = canMutateCatalogue(user);
  const identity = workspaceIdentity(user);
  const [leadResult, setLeadResult] = useState<{
    identity: string;
    rows: SupplierLeadTimeRow[];
    failed?: boolean;
  } | null>(null);
  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    getSupplierLeadTimes()
      .then((report) => {
        if (!cancelled) setLeadResult({ identity, rows: report.rows });
      })
      .catch(() => {
        if (!cancelled) setLeadResult({ identity, rows: [], failed: true });
      });
    return () => {
      cancelled = true;
    };
  }, [identity, user]);
  const leadTimes = supplierLeadTimeById(
    leadResult?.identity === identity ? leadResult.rows : [],
  );
  const observedLead = (id: string) =>
    leadResult?.identity !== identity
      ? "Loading…"
      : leadResult.failed
        ? "Unavailable"
        : formatObservedMedianLine(leadTimes.get(id));
  const [refreshKey, refresh] = useState(0);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Supplier | null>(null);
  const [form, setForm] = useState<CreateSupplierPayload>({
    name: "",
    default_currency: "USD",
    vat_number: "",
    address: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const start = (item?: Supplier) => {
    setEditing(item ?? null);
    setForm({
      name: item?.name ?? "",
      default_currency: item?.default_currency ?? "USD",
      vat_number: item?.vat_number ?? "",
      address: item?.address ?? "",
    });
    setError(null);
    setOpen(true);
  };
  async function save() {
    setBusy(true);
    setError(null);
    try {
      const payload = {
        ...form,
        name: form.name.trim(),
        default_currency: form.default_currency?.trim().toUpperCase(),
        vat_number: form.vat_number?.trim() || null,
        address: form.address?.trim() || null,
      };
      if (editing)
        await apiFetch<Supplier>(`/suppliers/${editing.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
      else await createSupplier(payload);
      setOpen(false);
      refresh((n) => n + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save supplier.");
    } finally {
      setBusy(false);
    }
  }
  const adapter: RecordWorkspaceAdapter<Supplier> = {
    resource: "suppliers",
    title: "Suppliers",
    singular: "supplier",
    breadcrumb: "Catalogue management",
    description:
      "Find supplier accounts, review purchasing history and manage supplier details.",
    columns: [
      {
        key: "name",
        label: "Supplier",
        render: (item) => item.name,
        sortable: true,
      },
      {
        key: "default_currency",
        label: "Currency",
        render: (item) => item.default_currency,
        sortable: true,
      },
      {
        key: "observed_lead_time",
        label: "Observed median",
        render: (item) => observedLead(item.id),
      },
    ],
    filters: [
      { key: "name", label: "Name", type: "text" },
      {
        key: "default_currency",
        label: "Currency",
        type: "enum",
        options: currencies,
        quick: true,
        allLabel: "All currencies",
      },
      { key: "vat_number", label: "VAT number", type: "text" },
      { key: "address", label: "Address", type: "text" },
    ],
    bulkFields: [
      { key: "default_currency", label: "Default currency", type: "text" },
    ],
    lifecycle: { activeLabel: "Active", archivedLabel: "Archived" },
    actions: allowed
      ? [
          { key: "edit", label: "Edit" },
          { key: "archive", label: "Archive" },
          { key: "restore", label: "Restore" },
        ]
      : [],
    getTitle: (item) => item.name,
    getSubtitle: (item) => item.default_currency,
    canEdit: (item) => !item.is_archived,
  };
  return (
    <>
      <RecordWorkspace
        adapter={adapter}
        refreshKey={refreshKey}
        onCreate={allowed ? () => start() : undefined}
        onEdit={allowed ? (item) => start(item) : undefined}
        loadingDetails={{
          tabs: ["Overview", "Records", "History"],
          fields: ["Default currency", "Observed lead time", "VAT number", "Address", "Status"],
        }}
        renderDetails={(item) => (
          <Tabs>
            <TabList aria-label="Supplier information">
              <Tab>Overview</Tab>
              <Tab>Records</Tab>
              <Tab>History</Tab>
            </TabList>
            <TabPanels>
              <TabPanel>
                <RecordDetails>
                  <RecordDetail label="Default currency">
                    {item.default_currency}
                  </RecordDetail>
                  <RecordDetail label="Observed lead time">
                    {observedLead(item.id)}
                  </RecordDetail>
                  <RecordDetail label="VAT number">
                    {item.vat_number}
                  </RecordDetail>
                  <RecordDetail label="Address">{item.address}</RecordDetail>
                  <RecordDetail label="Status">
                    {item.is_archived ? "Archived" : "Active"}
                  </RecordDetail>
                </RecordDetails>
              </TabPanel>
              <TabPanel>
                <PartyRecords key={item.id} kind="suppliers" id={item.id} />
              </TabPanel>
              <TabPanel>
                <Stack gap={6}>
                  <SupplierPricesTable
                    key={`prices-${item.id}`}
                    supplierId={item.id}
                  />
                  <PurchaseHistoryTable
                    key={`history-${item.id}`}
                    supplierId={item.id}
                  />
                </Stack>
              </TabPanel>
            </TabPanels>
          </Tabs>
        )}
      />
      <Modal
        open={open}
        modalHeading={editing ? "Edit supplier" : "New supplier"}
        primaryButtonText={busy ? "Saving…" : "Save supplier"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={
          busy ||
          !form.name.trim() ||
          !/^[A-Za-z]{3}$/.test(form.default_currency ?? "")
        }
        onRequestClose={() => {
          if (!busy) setOpen(false);
        }}
        onRequestSubmit={() => void save()}
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
          <TextInput
            id="supplier-name"
            disabled={busy}
            labelText="Name"
            value={form.name}
            onChange={(event) =>
              setForm((current) => ({ ...current, name: event.target.value }))
            }
            required
          />
          <TextInput
            id="supplier-currency"
            disabled={busy}
            labelText="Default currency"
            helperText="Three-letter currency code, for example ZAR or USD."
            value={form.default_currency ?? ""}
            maxLength={3}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                default_currency: event.target.value.toUpperCase(),
              }))
            }
          />
          <TextInput
            id="supplier-vat"
            disabled={busy}
            labelText="VAT number"
            value={form.vat_number ?? ""}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                vat_number: event.target.value,
              }))
            }
          />
          <TextArea
            id="supplier-address"
            disabled={busy}
            labelText="Address"
            value={form.address ?? ""}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                address: event.target.value,
              }))
            }
          />
        </Stack>
      </Modal>
    </>
  );
}

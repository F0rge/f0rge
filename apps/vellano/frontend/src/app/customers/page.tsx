"use client";

import {
  Button,
  DataTable,
  InlineNotification,
  Modal,
  Pagination,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  Tag,
  TextInput,
} from "@carbon/react";
import { DocumentExport, Edit } from "@carbon/icons-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { CustomerCrmBadges } from "@/components/customer-crm-badges";
import {
  CustomerFormFields,
  customerWritePayload,
  emptyCustomerForm,
  formFromCustomer,
} from "@/components/customer-form-fields";
import {
  CUSTOMER_TYPE_LABELS,
  canManageCustomerCredit,
  canMutateCustomers,
  createCustomer,
  formatZarAmount,
  listCustomers,
  updateCustomer,
  type CreateCustomerPayload,
  type CustomerCrm,
  type CustomerType,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { downloadCsv } from "@/lib/csv";
import { formatIsoDate, laybyActiveBadgeLabel, overdueBadgeLabel } from "@/lib/customer-crm";

const TABLE_HEADERS = [
  { key: "customer", header: "Customer" },
  { key: "type_tier", header: "Type & Tier" },
  { key: "contact", header: "Contact" },
  { key: "open_invoices", header: "Open Invoices" },
  { key: "active_laybys", header: "Active Laybys" },
] as const;

const ACTIONS_HEADER = { key: "actions", header: "" };

const CSV_HEADERS = [
  "Customer",
  "Type",
  "Tier",
  "Email",
  "Phone",
  "Open invoices",
  "Active laybys",
  "Overdue",
  "Layby active",
  "Last purchase",
];

type TypeFilter = "all" | CustomerType;
type BalanceFilter = "any" | "open_invoices" | "active_laybys";

type CustomerRow = {
  id: string;
  customer: string;
  type_tier: string;
  contact: string;
  open_invoices: string;
  active_laybys: string;
  actions: string;
};

function formatContact(customer: CustomerCrm): string {
  const parts = [customer.email, customer.phone].filter(Boolean);
  return parts.length > 0 ? parts.join(" • ") : "—";
}

function formatOpenInvoices(customer: CustomerCrm): { amount: string; detail: string | null } {
  if (customer.open_invoices_count === 0) {
    return { amount: "—", detail: null };
  }
  return { amount: formatZarAmount(customer.open_invoices_zar), detail: null };
}

function formatActiveLaybys(customer: CustomerCrm): { amount: string; detail: string | null } {
  if (customer.active_laybys_count === 0) {
    return { amount: "—", detail: null };
  }
  const label = customer.active_laybys_count === 1 ? "1 layby" : `${customer.active_laybys_count} laybys`;
  return { amount: formatZarAmount(customer.active_laybys_zar), detail: label };
}

function customerTypeTagType(type: CustomerType): "blue" | "purple" {
  return type === "retail" ? "blue" : "purple";
}

function csvMoney(count: number, amount: string): string {
  return count > 0 ? formatZarAmount(amount) : "";
}

export default function CustomersPage() {
  const router = useRouter();
  const { user } = useAuth();
  const canMutate = canMutateCustomers(user);
  const canEditCredit = canManageCustomerCredit(user);
  const [customers, setCustomers] = useState<CustomerCrm[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchFilter, setSearchFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("all");
  const [balanceFilter, setBalanceFilter] = useState<BalanceFilter>("any");
  const [overdueFilter, setOverdueFilter] = useState(false);
  const [activeLaybyFilter, setActiveLaybyFilter] = useState(false);
  const [onHoldFilter, setOnHoldFilter] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<CreateCustomerPayload>(emptyCustomerForm);
  const [editCustomer, setEditCustomer] = useState<CustomerCrm | null>(null);
  const [editForm, setEditForm] = useState<CreateCustomerPayload>(emptyCustomerForm);
  const [saving, setSaving] = useState(false);

  const loadCustomers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listCustomers({
        overdue: overdueFilter || undefined,
        active_layby: activeLaybyFilter || undefined,
        on_hold: onHoldFilter || undefined,
      });
      setCustomers(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load customers.");
    } finally {
      setLoading(false);
    }
  }, [overdueFilter, activeLaybyFilter, onHoldFilter]);

  useEffect(() => {
    if (user) {
      void loadCustomers();
    }
  }, [user, loadCustomers]);

  const filteredCustomers = useMemo(() => {
    const query = searchFilter.trim().toLowerCase();
    return customers.filter((customer) => {
      if (typeFilter !== "all" && customer.customer_type !== typeFilter) {
        return false;
      }
      if (balanceFilter === "open_invoices" && customer.open_invoices_count === 0) {
        return false;
      }
      if (balanceFilter === "active_laybys" && customer.active_laybys_count === 0) {
        return false;
      }
      if (!query) {
        return true;
      }
      return (
        customer.name.toLowerCase().includes(query) ||
        customer.id.toLowerCase().includes(query) ||
        (customer.email?.toLowerCase().includes(query) ?? false)
      );
    });
  }, [customers, searchFilter, typeFilter, balanceFilter]);

  useEffect(() => {
    setPage(1);
  }, [searchFilter, typeFilter, balanceFilter, overdueFilter, activeLaybyFilter, onHoldFilter]);

  const pagedCustomers = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filteredCustomers.slice(start, start + pageSize);
  }, [filteredCustomers, page, pageSize]);

  const tableHeaders = canMutate ? [...TABLE_HEADERS, ACTIONS_HEADER] : [...TABLE_HEADERS];

  const rows: CustomerRow[] = pagedCustomers.map((entry) => ({
    id: entry.id,
    customer: entry.id,
    type_tier: entry.id,
    contact: entry.id,
    open_invoices: entry.id,
    active_laybys: entry.id,
    actions: entry.id,
  }));

  function openCustomer(entry: CustomerCrm) {
    setEditCustomer(entry);
    setEditForm(formFromCustomer(entry));
  }

  function handleExport() {
    downloadCsv(
      "vellano-customers.csv",
      CSV_HEADERS,
      filteredCustomers.map((customer) => [
        customer.name,
        CUSTOMER_TYPE_LABELS[customer.customer_type],
        customer.price_tier,
        customer.email ?? "",
        customer.phone ?? "",
        csvMoney(customer.open_invoices_count, customer.open_invoices_zar),
        csvMoney(customer.active_laybys_count, customer.active_laybys_zar),
        customer.overdue_invoices_count > 0 ? overdueBadgeLabel(customer) : "",
        customer.active_laybys_count > 0 ? laybyActiveBadgeLabel(customer) : "",
        formatIsoDate(customer.last_purchase_date),
      ]),
    );
  }

  async function handleCreate() {
    const name = createForm.name.trim();
    if (!name) {
      setError("Customer name is required.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createCustomer(customerWritePayload(createForm, canEditCredit));
      setCreateOpen(false);
      setCreateForm(emptyCustomerForm);
      await loadCustomers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create customer.");
    } finally {
      setSaving(false);
    }
  }

  async function handleUpdate() {
    if (!editCustomer || !canMutate) {
      return;
    }
    const name = editForm.name.trim();
    if (!name) {
      setError("Customer name is required.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await updateCustomer(editCustomer.id, customerWritePayload(editForm, canEditCredit));
      setEditCustomer(null);
      setEditForm(emptyCustomerForm);
      await loadCustomers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update customer.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Stack gap={6}>
      <div className="vellano-page-header">
        <div>
          <h1 className="cds--type-productive-heading-04">Customers CRM</h1>
          <p className="cds--type-body-01">
            Manage retail and trade customers, view balances, laybys, and pricing tiers.
          </p>
        </div>
        <div className="vellano-catalogue-actions">
          <Button
            kind="secondary"
            renderIcon={DocumentExport}
            disabled={filteredCustomers.length === 0}
            onClick={handleExport}
          >
            Export CSV
          </Button>
          {canMutate ? (
            <Button
              onClick={() => {
                setCreateForm(emptyCustomerForm);
                setCreateOpen(true);
              }}
            >
              New customer
            </Button>
          ) : null}
        </div>
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

      <div className="vellano-catalogue-panel">
        <div className="vellano-catalogue-toolbar">
          <div className="vellano-catalogue-toolbar__left">
            <TextInput
              id="customers-search"
              labelText="Filter customers"
              hideLabel
              placeholder="Filter by name, email, or ID…"
              value={searchFilter}
              onChange={(event) => setSearchFilter(event.target.value)}
            />
            <span className="vellano-catalogue-toolbar__divider" aria-hidden />
            <div className="vellano-catalogue-chips" role="group" aria-label="Customer type filter">
              <Button
                kind={typeFilter === "all" ? "primary" : "ghost"}
                size="sm"
                onClick={() => setTypeFilter("all")}
              >
                All Types
              </Button>
              <Button
                kind={typeFilter === "retail" ? "primary" : "ghost"}
                size="sm"
                onClick={() => setTypeFilter("retail")}
              >
                Retail
              </Button>
              <Button
                kind={typeFilter === "trade" ? "primary" : "ghost"}
                size="sm"
                onClick={() => setTypeFilter("trade")}
              >
                Trade
              </Button>
            </div>
            <span className="vellano-catalogue-toolbar__divider" aria-hidden />
            <div className="vellano-catalogue-chips" role="group" aria-label="Balance filter">
              <Button
                kind={balanceFilter === "any" ? "primary" : "ghost"}
                size="sm"
                onClick={() => setBalanceFilter("any")}
              >
                Any balance
              </Button>
              <Button
                kind={balanceFilter === "open_invoices" ? "primary" : "ghost"}
                size="sm"
                onClick={() => setBalanceFilter("open_invoices")}
              >
                Has open invoices
              </Button>
              <Button
                kind={balanceFilter === "active_laybys" ? "primary" : "ghost"}
                size="sm"
                onClick={() => setBalanceFilter("active_laybys")}
              >
                Has active laybys
              </Button>
            </div>
            <span className="vellano-catalogue-toolbar__divider" aria-hidden />
            <div className="vellano-catalogue-chips" role="group" aria-label="CRM filters">
              <Button
                kind={overdueFilter ? "primary" : "ghost"}
                size="sm"
                onClick={() => setOverdueFilter((current) => !current)}
              >
                Overdue
              </Button>
              <Button
                kind={activeLaybyFilter ? "primary" : "ghost"}
                size="sm"
                onClick={() => setActiveLaybyFilter((current) => !current)}
              >
                Active layby
              </Button>
              <Button
                kind={onHoldFilter ? "primary" : "ghost"}
                size="sm"
                onClick={() => setOnHoldFilter((current) => !current)}
              >
                On hold
              </Button>
            </div>
          </div>
        </div>

        {loading ? (
          <p className="cds--type-body-01" style={{ padding: "1rem" }}>
            Loading customers…
          </p>
        ) : customers.length === 0 ? (
          <InlineNotification
            kind="info"
            title="No customers"
            subtitle="No customers match the current filters."
            hideCloseButton
            lowContrast
            style={{ margin: "1rem" }}
          />
        ) : (
          <>
            <DataTable rows={rows} headers={tableHeaders}>
              {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
                <TableContainer title="Customers" description="Retail and trade customer balances">
                  <Table {...getTableProps()}>
                    <TableHead>
                      <TableRow>
                        {headers.map((header) => (
                          <TableHeader
                            {...getHeaderProps({ header })}
                            key={header.key}
                            isSortable={false}
                          >
                            {header.header}
                          </TableHeader>
                        ))}
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {tableRows.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={headers.length}>
                            No customers match the current filters.
                          </TableCell>
                        </TableRow>
                      ) : (
                        tableRows.map((row) => {
                          const entry = pagedCustomers.find((customer) => customer.id === row.id);
                          if (!entry) {
                            return null;
                          }
                          const invoices = formatOpenInvoices(entry);
                          const laybys = formatActiveLaybys(entry);
                          return (
                            <TableRow {...getRowProps({ row })} key={row.id}>
                              <TableCell className="vellano-customer-cell">
                                <Button
                                  type="button"
                                  kind="ghost"
                                  size="sm"
                                  onClick={() => router.push(`/customers/${entry.id}`)}
                                  style={{ paddingInlineStart: 0 }}
                                >
                                  {entry.name}
                                </Button>
                                <CustomerCrmBadges customer={entry} />
                              </TableCell>
                              <TableCell>
                                <Tag type={customerTypeTagType(entry.customer_type)} size="sm">
                                  {CUSTOMER_TYPE_LABELS[entry.customer_type]}
                                </Tag>
                                <div className="vellano-muted-text" style={{ marginTop: "0.25rem" }}>
                                  Tier: {entry.price_tier}
                                </div>
                              </TableCell>
                              <TableCell className="vellano-cell-wrap">
                                <div className="cds--type-body-compact-01 vellano-break-text">
                                  {formatContact(entry)}
                                </div>
                              </TableCell>
                              <TableCell style={{ textAlign: "right" }}>
                                <div
                                  className="cds--type-body-compact-01"
                                  style={{ fontWeight: invoices.amount === "—" ? 400 : 600 }}
                                >
                                  {invoices.amount}
                                </div>
                              </TableCell>
                              <TableCell style={{ textAlign: "right" }}>
                                <div
                                  className="cds--type-body-compact-01"
                                  style={{ fontWeight: laybys.amount === "—" ? 400 : 600 }}
                                >
                                  {laybys.amount}
                                </div>
                                {laybys.detail ? (
                                  <div className="vellano-muted-text">{laybys.detail}</div>
                                ) : null}
                              </TableCell>
                              {canMutate ? (
                                <TableCell style={{ textAlign: "center" }}>
                                  <Button
                                    type="button"
                                    kind="ghost"
                                    size="sm"
                                    hasIconOnly
                                    iconDescription="Edit customer"
                                    renderIcon={Edit}
                                    onClick={(event) => {
                                      event.preventDefault();
                                      event.stopPropagation();
                                      openCustomer(entry);
                                    }}
                                  />
                                </TableCell>
                              ) : null}
                            </TableRow>
                          );
                        })
                      )}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </DataTable>
            <Pagination
              page={page}
              pageSize={pageSize}
              pageSizes={[10, 25, 50]}
              totalItems={filteredCustomers.length}
              onChange={({ page: nextPage, pageSize: nextSize }) => {
                setPage(nextPage);
                setPageSize(nextSize);
              }}
            />
          </>
        )}
      </div>

      <Modal
        open={createOpen}
        modalHeading="New customer"
        primaryButtonText="Create customer"
        secondaryButtonText="Cancel"
        onRequestClose={() => setCreateOpen(false)}
        onRequestSubmit={() => void handleCreate()}
        primaryButtonDisabled={saving || !createForm.name.trim()}
        size="md"
      >
        <CustomerFormFields
          idPrefix="create-customer"
          form={createForm}
          onChange={(patch) => setCreateForm((form) => ({ ...form, ...patch }))}
          showCreditFields={canEditCredit}
        />
      </Modal>

      <Modal
        open={editCustomer !== null}
        modalHeading="Edit customer"
        primaryButtonText="Save"
        secondaryButtonText="Cancel"
        onRequestClose={() => {
          setEditCustomer(null);
          setEditForm(emptyCustomerForm);
        }}
        onRequestSubmit={() => void handleUpdate()}
        primaryButtonDisabled={saving || !editForm.name.trim()}
        size="md"
      >
        <CustomerFormFields
          idPrefix="edit-customer"
          form={editForm}
          onChange={(patch) => setEditForm((form) => ({ ...form, ...patch }))}
          showCreditFields={canEditCredit}
        />
      </Modal>
    </Stack>
  );
}

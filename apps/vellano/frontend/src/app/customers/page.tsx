"use client";

import {
  Button,
  DataTable,
  InlineNotification,
  Modal,
  Select,
  SelectItem,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableHeader,
  TableRow,
  Tag,
  TextArea,
  TextInput,
} from "@carbon/react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  CUSTOMER_TYPE_LABELS,
  canMutateCustomers,
  createCustomer,
  formatZarAmount,
  listCustomers,
  type CreateCustomerPayload,
  type CustomerCrm,
  type CustomerType,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "customer", header: "Customer" },
  { key: "type_tier", header: "Type & Tier" },
  { key: "contact", header: "Contact" },
  { key: "open_invoices", header: "Open Invoices" },
  { key: "active_laybys", header: "Active Laybys" },
] as const;

type TypeFilter = "all" | CustomerType;
type BalanceFilter = "any" | "open_invoices" | "active_laybys";

type CustomerRow = {
  id: string;
  customer: string;
  type_tier: string;
  contact: string;
  open_invoices: string;
  active_laybys: string;
};

const emptyCreateForm: CreateCustomerPayload = {
  name: "",
  customer_type: "retail",
  price_tier: "standard",
  email: "",
  phone: "",
  vat_number: "",
  billing_address: "",
};

function formatContact(customer: CustomerCrm): string {
  const parts = [customer.email, customer.phone].filter(Boolean);
  return parts.length > 0 ? parts.join(" • ") : "—";
}

function formatOpenInvoices(customer: CustomerCrm): { amount: string; detail: string | null } {
  if (customer.open_invoices_count === 0) {
    return { amount: "—", detail: null };
  }
  const detail =
    customer.overdue_invoices_count > 0
      ? `${customer.overdue_invoices_count} overdue`
      : null;
  return { amount: formatZarAmount(customer.open_invoices_zar), detail };
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

export default function CustomersPage() {
  const { user } = useAuth();
  const canMutate = canMutateCustomers(user?.role);
  const [customers, setCustomers] = useState<CustomerCrm[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchFilter, setSearchFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("all");
  const [balanceFilter, setBalanceFilter] = useState<BalanceFilter>("any");
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<CreateCustomerPayload>(emptyCreateForm);
  const [saving, setSaving] = useState(false);

  const loadCustomers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listCustomers();
      setCustomers(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load customers.");
    } finally {
      setLoading(false);
    }
  }, []);

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

  const rows: CustomerRow[] = filteredCustomers.map((entry) => ({
    id: entry.id,
    customer: entry.id,
    type_tier: entry.id,
    contact: entry.id,
    open_invoices: entry.id,
    active_laybys: entry.id,
  }));

  async function handleCreate() {
    const name = createForm.name.trim();
    if (!name) {
      setError("Customer name is required.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createCustomer({
        name,
        customer_type: createForm.customer_type ?? "retail",
        price_tier: createForm.price_tier?.trim() || "standard",
        email: createForm.email,
        phone: createForm.phone,
        vat_number: createForm.vat_number,
        billing_address: createForm.billing_address,
      });
      setCreateOpen(false);
      setCreateForm(emptyCreateForm);
      await loadCustomers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create customer.");
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
        {canMutate ? (
          <Button onClick={() => setCreateOpen(true)}>New customer</Button>
        ) : null}
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
            subtitle="No customers have been added yet."
            hideCloseButton
            lowContrast
            style={{ margin: "1rem" }}
          />
        ) : (
          <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
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
                        const entry = filteredCustomers.find((customer) => customer.id === row.id);
                        if (!entry) {
                          return null;
                        }
                        const invoices = formatOpenInvoices(entry);
                        const laybys = formatActiveLaybys(entry);
                        return (
                          <TableRow {...getRowProps({ row })} key={row.id}>
                            <TableCell>
                              <div className="cds--type-body-compact-01" style={{ fontWeight: 600 }}>
                                {entry.name}
                              </div>
                              <div className="vellano-muted-text">{entry.id}</div>
                            </TableCell>
                            <TableCell>
                              <Tag type={customerTypeTagType(entry.customer_type)} size="sm">
                                {CUSTOMER_TYPE_LABELS[entry.customer_type]}
                              </Tag>
                              <div className="vellano-muted-text" style={{ marginTop: "0.25rem" }}>
                                Tier: {entry.price_tier}
                              </div>
                            </TableCell>
                            <TableCell>
                              <div className="cds--type-body-compact-01">{formatContact(entry)}</div>
                            </TableCell>
                            <TableCell style={{ textAlign: "right" }}>
                              <div
                                className="cds--type-body-compact-01"
                                style={{ fontWeight: invoices.amount === "—" ? 400 : 600 }}
                              >
                                {invoices.amount}
                              </div>
                              {invoices.detail ? (
                                <div
                                  className="vellano-muted-text"
                                  style={{ color: "var(--cds-support-error, #da1e28)" }}
                                >
                                  {invoices.detail}
                                </div>
                              ) : null}
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
                          </TableRow>
                        );
                      })
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </DataTable>
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
        <Stack gap={5}>
          <TextInput
            id="create-customer-name"
            labelText="Name"
            value={createForm.name}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, name: event.target.value }))
            }
            required
          />
          <Select
            id="create-customer-type"
            labelText="Customer type"
            value={createForm.customer_type ?? "retail"}
            onChange={(event) =>
              setCreateForm((form) => ({
                ...form,
                customer_type: event.target.value as CustomerType,
              }))
            }
          >
            <SelectItem value="retail" text="Retail" />
            <SelectItem value="trade" text="Trade" />
          </Select>
          <TextInput
            id="create-customer-tier"
            labelText="Price tier"
            value={createForm.price_tier ?? "standard"}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, price_tier: event.target.value }))
            }
          />
          <TextInput
            id="create-customer-email"
            labelText="Email"
            type="email"
            value={createForm.email ?? ""}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, email: event.target.value }))
            }
          />
          <TextInput
            id="create-customer-phone"
            labelText="Phone"
            value={createForm.phone ?? ""}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, phone: event.target.value }))
            }
          />
          <TextInput
            id="create-customer-vat"
            labelText="VAT number"
            value={createForm.vat_number ?? ""}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, vat_number: event.target.value }))
            }
          />
          <TextArea
            id="create-customer-billing"
            labelText="Billing address"
            value={createForm.billing_address ?? ""}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, billing_address: event.target.value }))
            }
          />
        </Stack>
      </Modal>
    </Stack>
  );
}

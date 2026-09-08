"use client";

import {
  Button,
  Checkbox,
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
  TextInput,
} from "@carbon/react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ACCOUNT_TYPES,
  TAX_TREATMENTS,
  canMutateBooks,
  createAccount,
  defaultTaxTreatment,
  formatZarAmount,
  listAccounts,
  listCategoryMaps,
  taxTreatmentLabel,
  updateAccount,
  upsertCategoryMap,
  type Account,
  type AccountType,
  type CategoryMap,
  type CreateAccountPayload,
  type TaxTreatment,
  type UpsertCategoryMapPayload,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "code", header: "Code" },
  { key: "name", header: "Name" },
  { key: "type", header: "Type" },
  { key: "tax", header: "Tax" },
  { key: "balance_zar", header: "Balance (ZAR)" },
  { key: "actions", header: "" },
] as const;

const MAP_HEADERS = [
  { key: "category", header: "Category" },
  { key: "sales_code", header: "Sales" },
  { key: "cogs_code", header: "COGS" },
  { key: "stock_adj_code", header: "Stock adj" },
  { key: "count_var_code", header: "Count var" },
  { key: "actions", header: "" },
] as const;

type AccountRow = {
  id: string;
  code: string;
  name: string;
  type: string;
  tax: string;
  balance_zar: string;
  actions: string;
};

type MapRow = {
  id: string;
  category: string;
  sales_code: string;
  cogs_code: string;
  stock_adj_code: string;
  count_var_code: string;
  actions: string;
};

const emptyCreateForm: CreateAccountPayload = {
  code: "",
  name: "",
  type: "asset",
  tax_treatment: "none",
};

const emptyMapForm: UpsertCategoryMapPayload = {
  category: "",
  sales_code: "",
  cogs_code: "",
  stock_adj_code: "",
  count_var_code: "",
};

function accountOptionLabel(account: Account): string {
  return `${account.code} — ${account.name}`;
}

function accountsOfType(accounts: Account[], type: AccountType): Account[] {
  return accounts.filter((account) => account.type === type && !account.is_archived);
}

export default function ChartOfAccountsPage() {
  const { user } = useAuth();
  const canMutate = canMutateBooks(user);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [maps, setMaps] = useState<CategoryMap[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [createForm, setCreateForm] = useState<CreateAccountPayload>(emptyCreateForm);
  const [editAccount, setEditAccount] = useState<Account | null>(null);
  const [editName, setEditName] = useState("");
  const [editArchived, setEditArchived] = useState(false);
  const [editTax, setEditTax] = useState<TaxTreatment>("none");
  const [mapOpen, setMapOpen] = useState(false);
  const [mapMode, setMapMode] = useState<"add" | "edit">("add");
  const [mapForm, setMapForm] = useState<UpsertCategoryMapPayload>(emptyMapForm);
  const [saving, setSaving] = useState(false);

  const incomeAccounts = useMemo(() => accountsOfType(accounts, "income"), [accounts]);
  const expenseAccounts = useMemo(() => accountsOfType(accounts, "expense"), [accounts]);

  const loadLedger = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [accountData, mapData] = await Promise.all([listAccounts(), listCategoryMaps()]);
      setAccounts(accountData);
      setMaps(mapData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load ledger.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadLedger();
    }
  }, [user, loadLedger]);

  const rows: AccountRow[] = accounts.map((entry) => ({
    id: entry.id,
    code: entry.code,
    name: entry.is_archived ? `${entry.name} (archived)` : entry.name,
    type: entry.type,
    tax: taxTreatmentLabel(entry.tax_treatment),
    balance_zar: formatZarAmount(entry.balance_zar),
    actions: entry.id,
  }));

  const mapRows: MapRow[] = maps.map((entry) => ({
    id: entry.id,
    category: entry.category,
    sales_code: entry.sales_code,
    cogs_code: entry.cogs_code,
    stock_adj_code: entry.stock_adj_code,
    count_var_code: entry.count_var_code,
    actions: entry.id,
  }));

  async function handleCreate() {
    setSaving(true);
    setError(null);
    try {
      await createAccount({
        code: createForm.code.trim(),
        name: createForm.name.trim(),
        type: createForm.type,
        tax_treatment: createForm.tax_treatment ?? defaultTaxTreatment(createForm.type),
      });
      setCreateOpen(false);
      setCreateForm(emptyCreateForm);
      await loadLedger();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create account.");
    } finally {
      setSaving(false);
    }
  }

  function openEdit(account: Account) {
    setEditAccount(account);
    setEditName(account.name);
    setEditArchived(account.is_archived);
    setEditTax(account.tax_treatment);
    setEditOpen(true);
  }

  async function handleEdit() {
    if (!editAccount) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await updateAccount(editAccount.id, {
        name: editName.trim(),
        is_archived: editArchived,
        tax_treatment: editTax,
      });
      setEditOpen(false);
      setEditAccount(null);
      await loadLedger();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update account.");
    } finally {
      setSaving(false);
    }
  }

  function openAddMap() {
    setMapMode("add");
    setMapForm(emptyMapForm);
    setMapOpen(true);
  }

  function openEditMap(entry: CategoryMap) {
    setMapMode("edit");
    setMapForm({
      category: entry.category,
      sales_code: entry.sales_code,
      cogs_code: entry.cogs_code,
      stock_adj_code: entry.stock_adj_code,
      count_var_code: entry.count_var_code,
    });
    setMapOpen(true);
  }

  const mapReady =
    mapForm.category.trim().length > 0 &&
    mapForm.sales_code !== "" &&
    mapForm.cogs_code !== "" &&
    mapForm.stock_adj_code !== "" &&
    mapForm.count_var_code !== "";

  async function handleSaveMap() {
    setSaving(true);
    setError(null);
    try {
      await upsertCategoryMap({
        category: mapForm.category.trim(),
        sales_code: mapForm.sales_code,
        cogs_code: mapForm.cogs_code,
        stock_adj_code: mapForm.stock_adj_code,
        count_var_code: mapForm.count_var_code,
      });
      setMapOpen(false);
      setMapForm(emptyMapForm);
      await loadLedger();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save category map.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Stack gap={6}>
      <div className="vellano-page-header">
        <div>
          <h1 className="cds--type-productive-heading-04">Chart of accounts</h1>
          <p className="cds--type-body-01">
            Double-entry ledger accounts with live ZAR balances.
          </p>
        </div>
        {canMutate ? <Button onClick={() => setCreateOpen(true)}>Add account</Button> : null}
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

      {loading ? (
        <p className="cds--type-body-01">Loading accounts…</p>
      ) : accounts.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No accounts"
          subtitle="No chart of accounts found."
          hideCloseButton
          lowContrast
        />
      ) : (
        <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
          {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Accounts" description="Vellano chart of accounts">
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
                  {tableRows.map((row) => {
                    const account = accounts.find((entry) => entry.id === row.id);
                    return (
                      <TableRow {...getRowProps({ row })} key={row.id}>
                        {row.cells.map((cell) => {
                          if (cell.info.header === "actions" && canMutate && account && !account.is_system) {
                            return (
                              <TableCell key={cell.id}>
                                <Button kind="ghost" size="sm" onClick={() => openEdit(account)}>
                                  Edit
                                </Button>
                              </TableCell>
                            );
                          }
                          if (cell.info.header === "actions") {
                            return <TableCell key={cell.id} />;
                          }
                          return <TableCell key={cell.id}>{cell.value}</TableCell>;
                        })}
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </DataTable>
      )}

      {!loading ? (
        <Stack gap={4}>
          <div className="vellano-page-header">
            <div>
              <h2 className="cds--type-productive-heading-03">Category posting</h2>
              <p className="cds--type-body-01">
                Sales, COGS, stock adjustment, and count variance accounts per catalogue category.
              </p>
            </div>
            {canMutate ? (
              <Button kind="secondary" onClick={openAddMap}>
                Add category map
              </Button>
            ) : null}
          </div>
          {maps.length === 0 ? (
            <InlineNotification
              kind="info"
              title="No category maps"
              subtitle="No category posting maps found."
              hideCloseButton
              lowContrast
            />
          ) : (
            <DataTable rows={mapRows} headers={[...MAP_HEADERS]}>
              {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
                <TableContainer title="Category maps" description="SKU category → ledger codes">
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
                      {tableRows.map((row) => {
                        const entry = maps.find((map) => map.id === row.id);
                        return (
                          <TableRow {...getRowProps({ row })} key={row.id}>
                            {row.cells.map((cell) => {
                              if (cell.info.header === "actions" && canMutate && entry) {
                                return (
                                  <TableCell key={cell.id}>
                                    <Button kind="ghost" size="sm" onClick={() => openEditMap(entry)}>
                                      Edit
                                    </Button>
                                  </TableCell>
                                );
                              }
                              if (cell.info.header === "actions") {
                                return <TableCell key={cell.id} />;
                              }
                              return <TableCell key={cell.id}>{cell.value}</TableCell>;
                            })}
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </DataTable>
          )}
        </Stack>
      ) : null}

      <Modal
        open={createOpen}
        modalHeading="Add account"
        primaryButtonText={saving ? "Adding…" : "Add"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || !createForm.code.trim() || !createForm.name.trim()}
        onRequestClose={() => setCreateOpen(false)}
        onRequestSubmit={() => void handleCreate()}
      >
        <Stack gap={5}>
          <TextInput
            id="create-account-code"
            labelText="Code"
            value={createForm.code}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, code: event.target.value }))
            }
            required
          />
          <TextInput
            id="create-account-name"
            labelText="Name"
            value={createForm.name}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, name: event.target.value }))
            }
            required
          />
          <Select
            id="create-account-type"
            labelText="Type"
            value={createForm.type}
            onChange={(event) => {
              const type = event.target.value as AccountType;
              setCreateForm((form) => ({
                ...form,
                type,
                tax_treatment: defaultTaxTreatment(type),
              }));
            }}
          >
            {ACCOUNT_TYPES.map((entry) => (
              <SelectItem key={entry.value} value={entry.value} text={entry.label} />
            ))}
          </Select>
          <Select
            id="create-account-tax"
            labelText="Tax treatment"
            value={createForm.tax_treatment ?? defaultTaxTreatment(createForm.type)}
            onChange={(event) =>
              setCreateForm((form) => ({
                ...form,
                tax_treatment: event.target.value as TaxTreatment,
              }))
            }
          >
            {TAX_TREATMENTS.map((entry) => (
              <SelectItem key={entry.value} value={entry.value} text={entry.label} />
            ))}
          </Select>
        </Stack>
      </Modal>

      <Modal
        open={editOpen}
        modalHeading="Edit account"
        primaryButtonText={saving ? "Saving…" : "Save"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || !editName.trim()}
        onRequestClose={() => setEditOpen(false)}
        onRequestSubmit={() => void handleEdit()}
      >
        <Stack gap={5}>
          <TextInput
            id="edit-account-name"
            labelText="Name"
            value={editName}
            onChange={(event) => setEditName(event.target.value)}
            required
          />
          <Select
            id="edit-account-tax"
            labelText="Tax treatment"
            value={editTax}
            onChange={(event) => setEditTax(event.target.value as TaxTreatment)}
          >
            {TAX_TREATMENTS.map((entry) => (
              <SelectItem key={entry.value} value={entry.value} text={entry.label} />
            ))}
          </Select>
          <Checkbox
            id="edit-account-archived"
            labelText="Archived"
            checked={editArchived}
            onChange={(_, { checked }) => setEditArchived(checked)}
          />
        </Stack>
      </Modal>

      <Modal
        open={mapOpen}
        modalHeading={mapMode === "add" ? "Add category map" : "Edit category map"}
        primaryButtonText={saving ? "Saving…" : "Save"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || !mapReady}
        onRequestClose={() => setMapOpen(false)}
        onRequestSubmit={() => void handleSaveMap()}
      >
        <Stack gap={5}>
          <TextInput
            id="category-map-name"
            labelText="Category"
            value={mapForm.category}
            onChange={(event) =>
              setMapForm((form) => ({ ...form, category: event.target.value }))
            }
            disabled={mapMode === "edit"}
            required
          />
          <Select
            id="category-map-sales"
            labelText="Sales account"
            value={mapForm.sales_code}
            onChange={(event) =>
              setMapForm((form) => ({ ...form, sales_code: event.target.value }))
            }
          >
            <SelectItem value="" text="Select an account" />
            {incomeAccounts.map((account) => (
              <SelectItem
                key={account.id}
                value={account.code}
                text={accountOptionLabel(account)}
              />
            ))}
          </Select>
          <Select
            id="category-map-cogs"
            labelText="COGS account"
            value={mapForm.cogs_code}
            onChange={(event) =>
              setMapForm((form) => ({ ...form, cogs_code: event.target.value }))
            }
          >
            <SelectItem value="" text="Select an account" />
            {expenseAccounts.map((account) => (
              <SelectItem
                key={account.id}
                value={account.code}
                text={accountOptionLabel(account)}
              />
            ))}
          </Select>
          <Select
            id="category-map-stock-adj"
            labelText="Stock adj account"
            value={mapForm.stock_adj_code}
            onChange={(event) =>
              setMapForm((form) => ({ ...form, stock_adj_code: event.target.value }))
            }
          >
            <SelectItem value="" text="Select an account" />
            {expenseAccounts.map((account) => (
              <SelectItem
                key={account.id}
                value={account.code}
                text={accountOptionLabel(account)}
              />
            ))}
          </Select>
          <Select
            id="category-map-count-var"
            labelText="Count var account"
            value={mapForm.count_var_code}
            onChange={(event) =>
              setMapForm((form) => ({ ...form, count_var_code: event.target.value }))
            }
          >
            <SelectItem value="" text="Select an account" />
            {expenseAccounts.map((account) => (
              <SelectItem
                key={account.id}
                value={account.code}
                text={accountOptionLabel(account)}
              />
            ))}
          </Select>
        </Stack>
      </Modal>
    </Stack>
  );
}

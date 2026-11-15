"use client";

import {
  Button,
  Checkbox,
  DataTable,
  InlineNotification,
  Modal,
  Pagination,
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
import { workspaceIdentity } from "@/lib/record-workspace";
import { RecordWorkspace, RecordDetails, RecordDetail, type RecordWorkspaceAdapter } from "@/components/record-workspace";
import { CLIENT_PAGE_SIZES, useClientPagination } from "@/lib/use-client-pagination";

const MAP_HEADERS = [
  { key: "category", header: "Category" },
  { key: "sales_code", header: "Sales" },
  { key: "cogs_code", header: "COGS" },
  { key: "stock_adj_code", header: "Stock adj" },
  { key: "count_var_code", header: "Count var" },
  { key: "actions", header: "" },
] as const;

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
  return <ChartOfAccountsContent key={workspaceIdentity(user)} />;
}

function ChartOfAccountsContent() {
  const { user } = useAuth();
  const canMutate = canMutateBooks(user);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [refreshKey, setRefreshKey] = useState(0);
  const [categoryOpen, setCategoryOpen] = useState(false);
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
  const [mapSearch, setMapSearch] = useState("");

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

  const filteredMaps = useMemo(() => {
    const query = mapSearch.trim().toLowerCase();
    if (!query) {
      return maps;
    }
    return maps.filter(
      (entry) =>
        entry.category.toLowerCase().includes(query) ||
        entry.sales_code.toLowerCase().includes(query) ||
        entry.cogs_code.toLowerCase().includes(query),
    );
  }, [maps, mapSearch]);

  const mapPage = useClientPagination(filteredMaps, mapSearch);

  const mapRows: MapRow[] = mapPage.pagedItems.map((entry) => ({
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
      setRefreshKey((value) => value + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create account.");
    } finally {
      setSaving(false);
    }
  }

  function openEdit(account: Account) {
    setError(null);
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
      setRefreshKey((value) => value + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update account.");
    } finally {
      setSaving(false);
    }
  }

  function openAddMap() {
    setCategoryOpen(false);
    setError(null);
    setMapMode("add");
    setMapForm(emptyMapForm);
    setMapOpen(true);
  }

  function openEditMap(entry: CategoryMap) {
    setCategoryOpen(false);
    setError(null);
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
      setCategoryOpen(true);
      setMapForm(emptyMapForm);
      await loadLedger();
      setRefreshKey((value) => value + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save category map.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Stack gap={6}>
      {error && !createOpen && !editOpen && !mapOpen && !categoryOpen ? (
        <InlineNotification
          kind="error"
          title="Error"
          subtitle={error}
          onCloseButtonClick={() => setError(null)}
          lowContrast
        />
      ) : null}

      <RecordWorkspace<Account>
        adapter={{
          resource: "accounts", title: "Chart of accounts", singular: "account", breadcrumb: "Books",
          description: "Review ledger accounts and their live ZAR balances.", defaultSort: "code",
          lifecycle: { activeLabel: "Active", archivedLabel: "Archived" },
          columns: [
            { key: "code", label: "Account / code", render: (item) => `${item.code} — ${item.name}`, sortable: true },
            { key: "type", label: "Type", render: (item) => ACCOUNT_TYPES.find((entry) => entry.value === item.type)?.label ?? item.type, sortable: true },
            { key: "balance_zar", label: "Balance", render: (item) => formatZarAmount(item.balance_zar), numeric: true, sortable: true },
          ],
          filters: [
            { key: "code", label: "Code", type: "text" },
            { key: "name", label: "Name", type: "text" },
            { key: "type", label: "Type", type: "enum", options: ACCOUNT_TYPES, quick: true },
            { key: "tax_treatment", label: "Tax treatment", type: "enum", options: TAX_TREATMENTS },
            { key: "balance_zar", label: "Balance", type: "number" },
          ],
          bulkFields: canMutate ? [
            { key: "tax_treatment", label: "Tax treatment", type: "enum", options: TAX_TREATMENTS },
            { key: "is_bank", label: "Bank account", type: "boolean" },
          ] : [],
          actions: canMutate ? [{ key: "edit", label: "Edit" }, { key: "archive", label: "Archive" }, { key: "restore", label: "Restore" }] : [],
          getTitle: (item) => item.name, getSubtitle: (item) => item.code,
          canEdit: (item) => canMutate && !item.is_system,
        } satisfies RecordWorkspaceAdapter<Account>}
        refreshKey={refreshKey}
        onCreate={canMutate ? () => { setError(null); setCreateOpen(true); } : undefined}
        createLabel="Add account"
        onEdit={canMutate ? openEdit : undefined}
        headerActions={<Button kind="tertiary" onClick={() => { setCategoryOpen(true); void loadLedger(); }}>Category posting</Button>}
        renderDetails={(item) => <Stack gap={5}>
          <div><p className="cds--type-label-01">Balance · ZAR</p><p className="cds--type-productive-heading-04">{formatZarAmount(item.balance_zar)}</p></div>
          <RecordDetails>
            <RecordDetail label="Code">{item.code}</RecordDetail>
            <RecordDetail label="Type">{ACCOUNT_TYPES.find((entry) => entry.value === item.type)?.label ?? item.type}</RecordDetail>
            <RecordDetail label="Tax treatment">{taxTreatmentLabel(item.tax_treatment)}</RecordDetail>
            <RecordDetail label="Status">{item.is_archived ? "Archived" : "Active"}</RecordDetail>
            <RecordDetail label="Bank account">{item.is_bank ? "Yes" : "No"}</RecordDetail>
            <RecordDetail label="Protection">{item.is_system ? "System account — protected" : "Custom account"}</RecordDetail>
          </RecordDetails>
          <p className="cds--type-body-01">Posted balances and journal history remain linked when an account is archived.</p>
        </Stack>}
      />

      <Modal open={categoryOpen} modalHeading="Category posting" passiveModal size="lg" onRequestClose={() => setCategoryOpen(false)}>
        {error && <InlineNotification kind="error" title="Could not save" subtitle={error} hideCloseButton lowContrast />}
        {loading ? <p role="status">Loading category posting…</p> : null}
      {!loading ? (
        <Stack gap={4}>
          <div className="firstout-page-header">
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
            <div className="firstout-catalogue-panel">
              <div className="firstout-catalogue-toolbar">
                <div className="firstout-catalogue-toolbar__left">
                  <TextInput
                    id="maps-search"
                    labelText="Filter category maps"
                    hideLabel
                    placeholder="Filter by category or code…"
                    value={mapSearch}
                    onChange={(event) => setMapSearch(event.target.value)}
                  />
                </div>
              </div>
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
                      {tableRows.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={headers.length}>No category maps match the current filter.</TableCell>
                        </TableRow>
                      ) : (
                      tableRows.map((row) => {
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
                      })
                      )}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </DataTable>
              <Pagination
                page={mapPage.page}
                pageSize={mapPage.pageSize}
                pageSizes={[...CLIENT_PAGE_SIZES]}
                totalItems={mapPage.totalItems}
                onChange={mapPage.onPaginationChange}
              />
            </div>
          )}
        </Stack>
      ) : null}

      </Modal>

      <Modal
        open={createOpen}
        modalHeading="Add account"
        primaryButtonText={saving ? "Adding…" : "Add"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={!canMutate || saving || !createForm.code.trim() || !createForm.name.trim()}
        onRequestClose={() => { if (!saving) setCreateOpen(false); }}
        onRequestSubmit={() => void handleCreate()}
      >
        <Stack gap={5}>
          {error && <InlineNotification kind="error" title="Could not save" subtitle={error} hideCloseButton lowContrast />}
          <TextInput
            id="create-account-code"
            disabled={saving}
            labelText="Code"
            value={createForm.code}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, code: event.target.value }))
            }
            required
          />
          <TextInput
            id="create-account-name"
            disabled={saving}
            labelText="Name"
            value={createForm.name}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, name: event.target.value }))
            }
            required
          />
          <Select
            id="create-account-type"
            disabled={saving}
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
            disabled={saving}
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
        primaryButtonDisabled={!canMutate || saving || !editName.trim()}
        onRequestClose={() => { if (!saving) setEditOpen(false); }}
        onRequestSubmit={() => void handleEdit()}
      >
        <Stack gap={5}>
          {error && <InlineNotification kind="error" title="Could not save" subtitle={error} hideCloseButton lowContrast />}
          <TextInput
            id="edit-account-name"
            disabled={saving}
            labelText="Name"
            value={editName}
            onChange={(event) => setEditName(event.target.value)}
            required
          />
          <Select
            id="edit-account-tax"
            disabled={saving}
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
            disabled={saving}
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
        primaryButtonDisabled={!canMutate || saving || !mapReady}
        onRequestClose={() => { if (!saving) { setMapOpen(false); setCategoryOpen(true); } }}
        onRequestSubmit={() => void handleSaveMap()}
      >
        <Stack gap={5}>
          {error && <InlineNotification kind="error" title="Could not save" subtitle={error} hideCloseButton lowContrast />}
          <TextInput
            id="category-map-name"
            labelText="Category"
            value={mapForm.category}
            onChange={(event) =>
              setMapForm((form) => ({ ...form, category: event.target.value }))
            }
            disabled={saving || mapMode === "edit"}
            required
          />
          <Select
            id="category-map-sales"
            disabled={saving}
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
            disabled={saving}
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
            disabled={saving}
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
            disabled={saving}
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

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
import { useCallback, useEffect, useState } from "react";

import {
  ACCOUNT_TYPES,
  canMutateBooks,
  createAccount,
  formatZarAmount,
  listAccounts,
  updateAccount,
  type Account,
  type AccountType,
  type CreateAccountPayload,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "code", header: "Code" },
  { key: "name", header: "Name" },
  { key: "type", header: "Type" },
  { key: "balance_zar", header: "Balance (ZAR)" },
  { key: "actions", header: "" },
] as const;

type AccountRow = {
  id: string;
  code: string;
  name: string;
  type: string;
  balance_zar: string;
  actions: string;
};

const emptyCreateForm: CreateAccountPayload = {
  code: "",
  name: "",
  type: "asset",
};

export default function ChartOfAccountsPage() {
  const { user } = useAuth();
  const canMutate = canMutateBooks(user?.role);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [createForm, setCreateForm] = useState<CreateAccountPayload>(emptyCreateForm);
  const [editAccount, setEditAccount] = useState<Account | null>(null);
  const [editName, setEditName] = useState("");
  const [editArchived, setEditArchived] = useState(false);
  const [saving, setSaving] = useState(false);

  const loadAccounts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listAccounts();
      setAccounts(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load accounts.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadAccounts();
    }
  }, [user, loadAccounts]);

  const rows: AccountRow[] = accounts.map((entry) => ({
    id: entry.id,
    code: entry.code,
    name: entry.is_archived ? `${entry.name} (archived)` : entry.name,
    type: entry.type,
    balance_zar: formatZarAmount(entry.balance_zar),
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
      });
      setCreateOpen(false);
      setCreateForm(emptyCreateForm);
      await loadAccounts();
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
      });
      setEditOpen(false);
      setEditAccount(null);
      await loadAccounts();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update account.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Stack gap={6}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
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
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, type: event.target.value as AccountType }))
            }
          >
            {ACCOUNT_TYPES.map((entry) => (
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
          <Checkbox
            id="edit-account-archived"
            labelText="Archived"
            checked={editArchived}
            onChange={(_, { checked }) => setEditArchived(checked)}
          />
        </Stack>
      </Modal>
    </Stack>
  );
}

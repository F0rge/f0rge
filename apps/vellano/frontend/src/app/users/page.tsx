"use client";

import {
  Button,
  DataTable,
  InlineNotification,
  Modal,
  PasswordInput,
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
  USER_ROLES,
  createUser,
  listUsers,
  updateUser,
  type CreateUserPayload,
  type User,
  type UserRole,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "email", header: "Email" },
  { key: "display_name", header: "Display name" },
  { key: "role", header: "Role" },
  { key: "team", header: "Team" },
  { key: "status", header: "Status" },
  { key: "actions", header: "Actions" },
] as const;

type UserRow = {
  id: string;
  email: string;
  display_name: string;
  role: string;
  team: string;
  status: string;
  actions: string;
};

const emptyCreateForm: CreateUserPayload = {
  email: "",
  password: "",
  role: "buyer",
};

export default function UsersPage() {
  const { user } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [editUser, setEditUser] = useState<User | null>(null);
  const [createForm, setCreateForm] = useState<CreateUserPayload>(emptyCreateForm);
  const [editForm, setEditForm] = useState({
    email: "",
    display_name: "",
    role: "buyer" as UserRole,
    password: "",
  });
  const [saving, setSaving] = useState(false);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listUsers();
      setUsers(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load users.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user?.role === "owner") {
      void loadUsers();
    }
  }, [user, loadUsers]);

  if (user?.role !== "owner") {
    return (
      <section className="vellano-forbidden">
        <InlineNotification
          kind="error"
          title="Forbidden"
          subtitle="Only owners can manage users."
          hideCloseButton
        />
      </section>
    );
  }

  const rows: UserRow[] = users.map((entry) => ({
    id: entry.id,
    email: entry.email,
    display_name: entry.display_name,
    role: entry.role,
    team: entry.team.name,
    status: entry.is_disabled ? "Disabled" : "Active",
    actions: entry.id,
  }));

  function openEdit(entry: User) {
    setEditUser(entry);
    setEditForm({
      email: entry.email,
      display_name: entry.display_name,
      role: entry.role,
      password: "",
    });
  }

  async function handleCreate() {
    setSaving(true);
    setError(null);
    try {
      await createUser(createForm);
      setCreateOpen(false);
      setCreateForm(emptyCreateForm);
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create user.");
    } finally {
      setSaving(false);
    }
  }

  async function handleEdit() {
    if (!editUser) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const payload: Parameters<typeof updateUser>[1] = {
        email: editForm.email,
        display_name: editForm.display_name,
        role: editForm.role,
      };
      if (editForm.password) {
        payload.password = editForm.password;
      }
      await updateUser(editUser.id, payload);
      setEditUser(null);
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update user.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDisable(entry: User) {
    setSaving(true);
    setError(null);
    try {
      await updateUser(entry.id, { is_disabled: true });
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to disable user.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Stack gap={6}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="cds--type-productive-heading-04">Users</h1>
          <p className="cds--type-body-01">Create and manage back-office accounts.</p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>Create user</Button>
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
        <p className="cds--type-body-01">Loading users…</p>
      ) : (
        <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
          {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Team members" description="All Vellano users">
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
                    const entry = users.find((u) => u.id === row.id);
                    return (
                      <TableRow {...getRowProps({ row })} key={row.id}>
                        {row.cells.map((cell) => {
                          if (cell.info.header === "actions" && entry) {
                            return (
                              <TableCell key={cell.id}>
                                <Stack gap={3} orientation="horizontal">
                                  <Button
                                    kind="ghost"
                                    size="sm"
                                    disabled={saving || entry.is_disabled}
                                    onClick={() => openEdit(entry)}
                                  >
                                    Edit
                                  </Button>
                                  <Button
                                    kind="danger--ghost"
                                    size="sm"
                                    disabled={saving || entry.is_disabled || entry.id === user.id}
                                    onClick={() => void handleDisable(entry)}
                                  >
                                    Disable
                                  </Button>
                                </Stack>
                              </TableCell>
                            );
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
        modalHeading="Create user"
        primaryButtonText={saving ? "Creating…" : "Create"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving}
        onRequestClose={() => setCreateOpen(false)}
        onRequestSubmit={() => void handleCreate()}
      >
        <Stack gap={5}>
          <TextInput
            id="create-email"
            labelText="Email"
            type="email"
            value={createForm.email}
            onChange={(event) => setCreateForm((f) => ({ ...f, email: event.target.value }))}
            required
          />
          <PasswordInput
            id="create-password"
            labelText="Password"
            value={createForm.password}
            onChange={(event) => setCreateForm((f) => ({ ...f, password: event.target.value }))}
            required
          />
          <TextInput
            id="create-display-name"
            labelText="Display name"
            value={createForm.display_name ?? ""}
            onChange={(event) =>
              setCreateForm((f) => ({ ...f, display_name: event.target.value || undefined }))
            }
          />
          <Select
            id="create-role"
            labelText="Role"
            value={createForm.role}
            onChange={(event) =>
              setCreateForm((f) => ({ ...f, role: event.target.value as UserRole }))
            }
          >
            {USER_ROLES.map((role) => (
              <SelectItem key={role.value} value={role.value} text={role.label} />
            ))}
          </Select>
        </Stack>
      </Modal>

      <Modal
        open={editUser !== null}
        modalHeading="Edit user"
        primaryButtonText={saving ? "Saving…" : "Save"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving}
        onRequestClose={() => setEditUser(null)}
        onRequestSubmit={() => void handleEdit()}
      >
        <Stack gap={5}>
          <TextInput
            id="edit-email"
            labelText="Email"
            type="email"
            value={editForm.email}
            onChange={(event) => setEditForm((f) => ({ ...f, email: event.target.value }))}
          />
          <TextInput
            id="edit-display-name"
            labelText="Display name"
            value={editForm.display_name}
            onChange={(event) =>
              setEditForm((f) => ({ ...f, display_name: event.target.value }))
            }
          />
          <Select
            id="edit-role"
            labelText="Role"
            value={editForm.role}
            onChange={(event) =>
              setEditForm((f) => ({ ...f, role: event.target.value as UserRole }))
            }
          >
            {USER_ROLES.map((role) => (
              <SelectItem key={role.value} value={role.value} text={role.label} />
            ))}
          </Select>
          <PasswordInput
            id="edit-password"
            labelText="New password"
            helperText="Leave blank to keep current password"
            value={editForm.password}
            onChange={(event) => setEditForm((f) => ({ ...f, password: event.target.value }))}
          />
        </Stack>
      </Modal>
    </Stack>
  );
}

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
  TextInput,
} from "@carbon/react";
import { useCallback, useEffect, useState } from "react";

import {
  can,
  isActiveLocation,
  listLocations,
  listRoles,
  listUsers,
  updateUser,
  type Location,
  type Role,
  type User,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { userEditPayload } from "@/lib/user-edit";

const TABLE_HEADERS = [
  { key: "email", header: "Contact email" },
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

export default function UsersPage() {
  const { user } = useAuth();
  const canManageUsers = can(user, "users.manage");
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editUser, setEditUser] = useState<User | null>(null);
  const [editForm, setEditForm] = useState({
    display_name: "",
    role: "buyer",
    default_location_id: "",
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
    if (canManageUsers) {
      void loadUsers();
      void listRoles()
        .then((data) => setRoles(data))
        .catch(() => setRoles([]));
      void listLocations()
        .then((data) => setLocations(data.filter(isActiveLocation)))
        .catch(() => setLocations([]));
    }
  }, [canManageUsers, loadUsers]);

  if (!user || !canManageUsers) {
    return (
      <section className="firstout-forbidden">
        <InlineNotification
          kind="error"
          title="Forbidden"
          subtitle="You do not have permission to manage users."
          hideCloseButton
        />
      </section>
    );
  }

  const roleNameBySlug = Object.fromEntries(roles.map((role) => [role.slug, role.name]));

  const rows: UserRow[] = users.map((entry) => ({
    id: entry.id,
    email: entry.email,
    display_name: entry.display_name,
    role: roleNameBySlug[entry.role] ?? entry.role,
    team: entry.team.name,
    status: entry.is_disabled ? "Disabled" : "Active",
    actions: entry.id,
  }));

  function openEdit(entry: User) {
    setEditUser(entry);
    setEditForm({
      display_name: entry.display_name,
      role: entry.role,
      default_location_id: entry.default_location_id ?? "",
    });
  }

  function defaultLocationSelect(
    id: string,
    labelText: string,
    value: string,
    onChange: (next: string) => void,
  ) {
    return (
      <Select
        id={id}
        labelText={labelText}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        <SelectItem value="" text="No default" />
        {locations.map((loc) => (
          <SelectItem
            key={loc.id}
            value={loc.id}
            text={`${loc.name} (${loc.type})`}
          />
        ))}
      </Select>
    );
  }

  async function handleEdit() {
    if (!editUser) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await updateUser(editUser.id, userEditPayload(editUser, editForm));
      setEditUser(null);
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update user.");
    } finally {
      setSaving(false);
    }
  }

  async function handleStatusChange(entry: User, isDisabled: boolean) {
    setSaving(true);
    setError(null);
    try {
      await updateUser(entry.id, { is_disabled: isDisabled });
      await loadUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${isDisabled ? "disable" : "enable"} user.`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Stack gap={6}>
      <div className="firstout-page-header">
        <div>
          <h1 className="cds--type-productive-heading-04">Users</h1>
          <p className="cds--type-body-01">Manage access and invite staff from organisation settings. Each person manages their sign-in details in Clerk.</p>
        </div>
        <Button href="/organisation">Invite staff</Button>
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
            <TableContainer title="Team members" description="All Firstout users">
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
                                    kind={entry.is_disabled ? "ghost" : "danger--ghost"}
                                    size="sm"
                                    disabled={saving || entry.id === user.id}
                                    onClick={() => void handleStatusChange(entry, !entry.is_disabled)}
                                  >
                                    {entry.is_disabled ? "Enable" : "Disable"}
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
        open={editUser !== null}
        className="firstout-modal--actions-end"
        modalHeading="Edit user"
        primaryButtonText={saving ? "Saving…" : "Save"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving}
        onRequestClose={() => setEditUser(null)}
        onRequestSubmit={() => void handleEdit()}
      >
        <Stack gap={5}>
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
              setEditForm((f) => ({ ...f, role: event.target.value }))
            }
          >
            {roles.map((role) => (
              <SelectItem key={role.slug} value={role.slug} text={role.name} />
            ))}
          </Select>
          {defaultLocationSelect(
            "edit-default-location",
            "Default location",
            editForm.default_location_id,
            (next) => setEditForm((f) => ({ ...f, default_location_id: next })),
          )}
        </Stack>
      </Modal>
    </Stack>
  );
}

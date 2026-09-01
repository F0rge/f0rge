"use client";

import {
  Button,
  Checkbox,
  DataTable,
  InlineNotification,
  Modal,
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
import { useCallback, useEffect, useState } from "react";

import {
  can,
  createRole,
  deleteRole,
  listRoles,
  type Role,
} from "@/lib/api";
import { PERMISSION_CATALOG } from "@/lib/permissions";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "name", header: "Name" },
  { key: "slug", header: "Slug" },
  { key: "permissions", header: "Permissions" },
  { key: "actions", header: "Actions" },
] as const;

type RoleRow = {
  id: string;
  name: string;
  slug: string;
  permissions: string;
  actions: string;
};

export default function RolesPage() {
  const { user } = useAuth();
  const canManageUsers = can(user, "users.manage");
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [name, setName] = useState("");
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  const loadRoles = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRoles(await listRoles());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load roles.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (canManageUsers) {
      void loadRoles();
    }
  }, [canManageUsers, loadRoles]);

  if (!user || !canManageUsers) {
    return (
      <section className="vellano-forbidden">
        <InlineNotification
          kind="error"
          title="Forbidden"
          subtitle="You do not have permission to manage roles."
          hideCloseButton
        />
      </section>
    );
  }

  const rows: RoleRow[] = roles.map((role) => ({
    id: role.id,
    name: role.name,
    slug: role.slug,
    permissions: role.permissions.join(", "),
    actions: role.id,
  }));

  function toggleKey(key: string) {
    setSelectedKeys((current) =>
      current.includes(key) ? current.filter((item) => item !== key) : [...current, key],
    );
  }

  function openCreate() {
    setName("");
    setSelectedKeys([]);
    setCreateOpen(true);
  }

  async function handleCreate() {
    const trimmed = name.trim();
    if (!trimmed) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createRole({ name: trimmed, permissions: selectedKeys });
      setCreateOpen(false);
      await loadRoles();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create role.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(role: Role) {
    setSaving(true);
    setError(null);
    try {
      await deleteRole(role.id);
      await loadRoles();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete role.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Stack gap={6}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="cds--type-productive-heading-04">Roles</h1>
          <p className="cds--type-body-01">
            Preset roles are read-only. Create a custom role, then assign it on Users.
          </p>
        </div>
        <Button onClick={openCreate}>Create role</Button>
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
        <p className="cds--type-body-01">Loading roles…</p>
      ) : (
        <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
          {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Roles" description="System presets and custom roles">
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
                    const entry = roles.find((role) => role.id === row.id);
                    return (
                      <TableRow {...getRowProps({ row })} key={row.id}>
                        {row.cells.map((cell) => {
                          if (cell.info.header === "name" && entry) {
                            return (
                              <TableCell key={cell.id}>
                                <Stack gap={2} orientation="horizontal">
                                  <span>{entry.name}</span>
                                  {entry.is_system ? (
                                    <Tag type="blue" size="sm">
                                      Preset
                                    </Tag>
                                  ) : null}
                                  {entry.is_owner_preset ? (
                                    <Tag type="high-contrast" size="sm">
                                      Immutable
                                    </Tag>
                                  ) : null}
                                </Stack>
                              </TableCell>
                            );
                          }
                          if (cell.info.header === "permissions" && entry) {
                            return (
                              <TableCell key={cell.id}>
                                {entry.permissions.length === 0 ? (
                                  "—"
                                ) : (
                                  <Stack gap={2} orientation="horizontal">
                                    {entry.permissions.map((key) => (
                                      <Tag key={key} type="gray" size="sm">
                                        {key}
                                      </Tag>
                                    ))}
                                  </Stack>
                                )}
                              </TableCell>
                            );
                          }
                          if (cell.info.header === "actions" && entry) {
                            return (
                              <TableCell key={cell.id}>
                                {entry.is_system ? (
                                  "—"
                                ) : (
                                  <Button
                                    kind="danger--ghost"
                                    size="sm"
                                    disabled={saving}
                                    onClick={() => void handleDelete(entry)}
                                  >
                                    Delete
                                  </Button>
                                )}
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
        modalHeading="Create role"
        primaryButtonText={saving ? "Creating…" : "Create"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || !name.trim()}
        onRequestClose={() => setCreateOpen(false)}
        onRequestSubmit={() => void handleCreate()}
      >
        <Stack gap={5}>
          <TextInput
            id="create-role-name"
            labelText="Name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />
          <fieldset className="cds--fieldset">
            <legend className="cds--label">Permissions</legend>
            <Stack gap={3}>
              {PERMISSION_CATALOG.map((key) => (
                <Checkbox
                  key={key}
                  id={`create-role-perm-${key}`}
                  labelText={key}
                  checked={selectedKeys.includes(key)}
                  onChange={() => toggleKey(key)}
                />
              ))}
            </Stack>
          </fieldset>
        </Stack>
      </Modal>
    </Stack>
  );
}

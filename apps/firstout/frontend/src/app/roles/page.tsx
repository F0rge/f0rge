"use client";

import { UserRole } from "@carbon/icons-react";
import { Checkbox, InlineNotification, Modal, Stack, Tag, TextInput } from "@carbon/react";
import { useRef, useState } from "react";
import { AdminPageHeader } from "@/components/administration";
import { RecordWorkspace, type RecordWorkspaceAdapter } from "@/components/record-workspace";
import { ADMIN_DESTINATIONS } from "@/lib/admin-navigation";
import { can, createRole, updateRole, type Role } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { PERMISSION_CATALOG, PERMISSION_LABELS, permissionLabel, type PermissionKey } from "@/lib/permissions";
import { workspaceIdentity } from "@/lib/record-workspace";
import { adminError } from "@/lib/staff-administration";
import styles from "./roles.module.css";

const permissionGroups = [
  { label: "Administration", keys: ["users.manage", "settings.mutate"] },
  { label: "Stock", keys: ["catalogue.mutate", "po.raise", "stock.receive", "stock.transfer", "stock.adjust", "stock.cost.view"] },
  { label: "Sales", keys: ["till.sell", "till.discount", "sales.returns", "sales.laybys", "sales.quotes", "sales.orders", "sales.refunds", "sales.deliveries", "sales.customers"] },
  { label: "Finance", keys: ["books.mutate", "books.journals"] },
] as const satisfies ReadonlyArray<{ label: string; keys: readonly PermissionKey[] }>;
const knownPermissions = new Set<string>(PERMISSION_CATALOG);

const { label, description } = ADMIN_DESTINATIONS.roles;
const adapter: RecordWorkspaceAdapter<Role> = {
  resource: "roles",
  title: label,
  singular: "role",
  plural: "roles",
  breadcrumb: "Administration",
  description,
  columns: [
    { key: "name", label: "Role", render: (item) => item.name, sortable: true },
    { key: "is_system", label: "Type", render: (item) => <Tag type={item.is_system ? "gray" : "blue"}>{item.is_system ? "Preset" : "Custom"}</Tag>, sortable: true },
    { key: "permissions", label: "Permissions", render: (item) => item.permissions.length, numeric: true },
  ],
  filters: [
    { key: "name", label: "Name", type: "text" },
    { key: "slug", label: "Role identifier", type: "text" },
    { key: "is_system", label: "System preset", type: "boolean", quick: true, allLabel: "All roles" },
    { key: "permissions", label: "Permission key", type: "text" },
  ],
  actions: [{ key: "delete", label: "Delete role", danger: true }],
  getTitle: (item) => item.name,
  getSubtitle: (item) => item.is_owner_preset ? "Owner preset" : item.is_system ? "System preset" : "Custom role",
  renderAvatar: () => <UserRole size={16} />,
  canEdit: (item) => !item.is_system,
};

function RoleDetails({ role }: { role: Role }) {
  const additionalPermissions = role.permissions.filter((key) => !knownPermissions.has(key));
  return (
    <Stack gap={5}>
      <p className="cds--type-body-01">
        {role.is_system ? "System presets are protected." : "A custom role can be deleted only when no staff members use it."}
      </p>
      <dl className={styles.identifier}>
        <dt className="cds--type-label-01">Role identifier</dt>
        <dd>{role.slug}</dd>
      </dl>
      <h2 className="cds--type-heading-03">Permissions</h2>
      {role.permissions.length > 0 ? (
        <div className={styles.permissionGroups}>
          {permissionGroups.map(({ label: group, keys }) => {
            const granted = keys.filter((key) => role.permissions.includes(key));
            return granted.length > 0 ? (
              <section key={group}>
                <h3>{group}</h3>
                <ul>{granted.map((key) => <li key={key}>{PERMISSION_LABELS[key]}</li>)}</ul>
              </section>
            ) : null;
          })}
          {additionalPermissions.length > 0 ? (
            <section><h3>Additional permissions</h3><ul>{additionalPermissions.map((key) => <li key={key}>{permissionLabel(key)}</li>)}</ul></section>
          ) : null}
        </div>
      ) : <p>No permissions assigned.</p>}
    </Stack>
  );
}

function RoleEditor({ role, onClose, onSaved }: { role: Role | null; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState(role?.name ?? "");
  const [permissions, setPermissions] = useState(role?.permissions ?? []);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const saving = useRef(false);
  const dirty = !role || name !== role.name || permissions.length !== role.permissions.length ||
    permissions.some((permission) => !role.permissions.includes(permission));

  async function save() {
    const trimmed = name.trim();
    if (saving.current || !trimmed || !dirty) return;
    saving.current = true;
    setBusy(true);
    setError("");
    try {
      if (role) await updateRole(role.id, { name: trimmed, permissions });
      else await createRole({ name: trimmed, permissions });
      onSaved();
    } catch (reason) {
      setError(adminError(reason, "Could not save this role."));
    } finally {
      saving.current = false;
      setBusy(false);
    }
  }

  return (
    <Modal
      open
      hasScrollingContent
      modalHeading={role ? "Edit custom role" : "Create role"}
      primaryButtonText={busy ? "Saving…" : "Save role"}
      secondaryButtonText="Cancel"
      primaryButtonDisabled={busy || !name.trim() || !dirty}
      selectorPrimaryFocus="#role-name"
      onRequestClose={() => { if (!saving.current) onClose(); }}
      onRequestSubmit={() => void save()}
    >
      <Stack gap={5}>
        {error && <InlineNotification kind="error" title="Could not save" subtitle={error} hideCloseButton lowContrast />}
        <TextInput id="role-name" disabled={busy} labelText="Name" value={name} maxLength={255}
          onChange={(event) => setName(event.target.value)} required />
        <div className={styles.permissionGroups}>
          {permissionGroups.map(({ label: group, keys }) => (
            <fieldset disabled={busy} key={group}>
              <legend>{group}</legend>
              {keys.map((key) => (
                <Checkbox key={key} id={`role-${key}`} labelText={PERMISSION_LABELS[key]} checked={permissions.includes(key)}
                  onChange={(_, { checked }) => setPermissions((current) => checked
                    ? [...current, key]
                    : current.filter((item) => item !== key))} />
              ))}
            </fieldset>
          ))}
        </div>
      </Stack>
    </Modal>
  );
}

function RolesScreen() {
  const [refreshKey, refresh] = useState(0);
  const [editor, setEditor] = useState<{ role: Role | null } | null>(null);
  const [notice, setNotice] = useState("");
  return (
    <Stack gap={5}>
      {notice ? <InlineNotification kind="success" title={notice} lowContrast onCloseButtonClick={() => setNotice("")} /> : null}
      <RecordWorkspace adapter={adapter} refreshKey={refreshKey} createLabel="Create role" listTitle="Role directory" modalDetails
        onCreate={() => setEditor({ role: null })}
        onEdit={(role) => setEditor({ role })}
        renderDetails={(role) => <RoleDetails role={role} />} />
      {editor ? (
        <RoleEditor role={editor.role} onClose={() => setEditor(null)} onSaved={() => {
          setNotice(editor.role ? "Role updated" : "Role created");
          setEditor(null);
          refresh((value) => value + 1);
        }} />
      ) : null}
    </Stack>
  );
}

export default function RolesPage() {
  const { user } = useAuth();
  if (can(user, "users.manage")) return <RolesScreen key={workspaceIdentity(user)} />;
  return (
    <Stack gap={6}>
      <AdminPageHeader title={label} description={description} />
      <InlineNotification kind="error" title="Role management unavailable" subtitle="You do not have permission to manage roles." hideCloseButton lowContrast />
    </Stack>
  );
}

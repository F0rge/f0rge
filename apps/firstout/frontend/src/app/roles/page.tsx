"use client";
import {
  Checkbox,
  InlineNotification,
  Modal,
  Stack,
  Tab,
  TabList,
  TabPanel,
  TabPanels,
  Tabs,
  Tag,
  TextInput,
} from "@carbon/react";
import { useState } from "react";
import {
  RecordDetail,
  RecordDetails,
  RecordWorkspace,
  type RecordWorkspaceAdapter,
} from "@/components/record-workspace";
import { can, createRole, updateRole, type Role } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { workspaceIdentity } from "@/lib/record-workspace";
import { PERMISSION_CATALOG } from "@/lib/permissions";

export default function RolesPage() {
  const { user } = useAuth();
  return <RolesScreen key={workspaceIdentity(user)} />;
}
function RolesScreen() {
  const { user } = useAuth();
  const allowed = can(user, "users.manage");
  const [refreshKey, refresh] = useState(0);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Role | null>(null);
  const [name, setName] = useState("");
  const [permissions, setPermissions] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const start = (role?: Role) => {
    setEditing(role ?? null);
    setName(role?.name ?? "");
    setPermissions(role?.permissions ?? []);
    setError(null);
    setOpen(true);
  };
  async function save() {
    setBusy(true);
    setError(null);
    try {
      if (editing)
        await updateRole(editing.id, { name: name.trim(), permissions });
      else await createRole({ name: name.trim(), permissions });
      setOpen(false);
      refresh((n) => n + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save role.");
    } finally {
      setBusy(false);
    }
  }
  const adapter: RecordWorkspaceAdapter<Role> = {
    resource: "roles",
    title: "Roles",
    singular: "role",
    breadcrumb: "Administration",
    description:
      "Review permission bundles and manage custom roles. System presets remain protected.",
    columns: [
      {
        key: "name",
        label: "Role",
        render: (item) => item.name,
        sortable: true,
      },
      {
        key: "slug",
        label: "Slug",
        render: (item) => item.slug,
        sortable: true,
      },
      {
        key: "permissions",
        label: "Permissions",
        render: (item) => item.permissions.length,
        numeric: true,
      },
    ],
    filters: [
      { key: "name", label: "Name", type: "text" },
      { key: "slug", label: "Slug", type: "text" },
      {
        key: "is_system",
        label: "System preset",
        type: "boolean",
        quick: true,
      },
      { key: "permissions", label: "Permission key", type: "text" },
    ],
    actions: allowed ? [{ key: "delete", label: "Delete", danger: true }] : [],
    getTitle: (item) => item.name,
    getSubtitle: (item) =>
      item.is_owner_preset
        ? "Owner preset · immutable"
        : item.is_system
          ? "System preset"
          : "Custom role",
    canEdit: (item) => !item.is_system,
  };
  if (!allowed)
    return (
      <InlineNotification
        kind="error"
        title="Forbidden"
        subtitle="You do not have permission to manage roles."
        hideCloseButton
      />
    );
  return (
    <>
      <RecordWorkspace
        adapter={adapter}
        refreshKey={refreshKey}
        onCreate={() => start()}
        onEdit={(item) => start(item)}
        renderDetails={(item) => (
          <Tabs>
            <TabList aria-label="Role information">
              <Tab>Overview</Tab>
              <Tab>Permissions</Tab>
            </TabList>
            <TabPanels>
              <TabPanel>
                <RecordDetails>
                  <RecordDetail label="Slug">{item.slug}</RecordDetail>
                  <RecordDetail label="Origin">
                    {item.is_system ? "System preset" : "Custom role"}
                  </RecordDetail>
                  <RecordDetail label="Permission count">
                    {item.permissions.length}
                  </RecordDetail>
                  <RecordDetail label="Protection">
                    {item.is_system
                      ? "Preset roles cannot be edited or deleted."
                      : "A custom role can be deleted only when no staff members use it."}
                  </RecordDetail>
                </RecordDetails>
              </TabPanel>
              <TabPanel>
                <div className="firstout-tag-wrap">
                  {item.permissions.map((key) => (
                    <Tag key={key} type="gray">
                      {key}
                    </Tag>
                  ))}
                </div>
              </TabPanel>
            </TabPanels>
          </Tabs>
        )}
      />
      <Modal
        open={open}
        modalHeading={editing ? "Edit custom role" : "Create role"}
        primaryButtonText={busy ? "Saving…" : "Save role"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={busy || !name.trim()}
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
            id="role-name"
            disabled={busy}
            labelText="Name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            required
          />
          <fieldset disabled={busy}>
            <legend className="cds--label">Permissions</legend>
            {PERMISSION_CATALOG.map((key) => (
              <Checkbox
                key={key}
                id={`role-${key}`}
                labelText={key}
                checked={permissions.includes(key)}
                onChange={(_, { checked }) =>
                  setPermissions((current) =>
                    checked
                      ? [...current, key]
                      : current.filter((item) => item !== key),
                  )
                }
              />
            ))}
          </fieldset>
        </Stack>
      </Modal>
    </>
  );
}

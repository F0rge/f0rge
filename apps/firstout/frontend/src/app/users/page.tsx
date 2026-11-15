"use client";
import {
  Button,
  InlineNotification,
  Modal,
  Select,
  SelectItem,
  Stack,
  TextInput,
} from "@carbon/react";
import { useEffect, useState } from "react";
import {
  RecordDetail,
  RecordDetails,
  RecordWorkspace,
  type RecordWorkspaceAdapter,
} from "@/components/record-workspace";
import {
  can,
  isActiveLocation,
  listLocations,
  listRoles,
  updateUser,
  type Location,
  type Role,
  type User,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { workspaceIdentity } from "@/lib/record-workspace";
import { userEditPayload } from "@/lib/user-edit";

export default function UsersPage() {
  const { user } = useAuth();
  return <UsersScreen key={workspaceIdentity(user)} />;
}
function UsersScreen() {
  const { user } = useAuth();
  const allowed = can(user, "users.manage");
  const identity = `${user?.team.id}:${user?.id}`;
  const [refreshKey, refresh] = useState(0);
  const [metadata, setMetadata] = useState<{
    identity: string;
    roles: Role[];
    locations: Location[];
    error?: string;
  } | null>(null);
  const [editing, setEditing] = useState<User | null>(null);
  const [form, setForm] = useState({
    display_name: "",
    role: "buyer",
    default_location_id: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!allowed) return;
    let cancelled = false;
    Promise.all([listRoles(), listLocations()])
      .then(([roles, locations]) => {
        if (!cancelled)
          setMetadata({
            identity,
            roles,
            locations: locations.filter(isActiveLocation),
          });
      })
      .catch((err: unknown) => {
        if (!cancelled)
          setMetadata({
            identity,
            roles: [],
            locations: [],
            error:
              err instanceof Error
                ? err.message
                : "Could not load roles and locations.",
          });
      });
    return () => {
      cancelled = true;
    };
  }, [allowed, identity, refreshKey]);
  const roles = metadata?.identity === identity ? metadata.roles : [];
  const locations = metadata?.identity === identity ? metadata.locations : [];
  const roleName = (slug: string) =>
    roles.find((role) => role.slug === slug)?.name ?? slug;
  async function save() {
    if (!editing) return;
    setBusy(true);
    setError(null);
    try {
      await updateUser(editing.id, userEditPayload(editing, form));
      setEditing(null);
      refresh((n) => n + 1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save user.");
    } finally {
      setBusy(false);
    }
  }
  const adapter: RecordWorkspaceAdapter<User> = {
    resource: "users",
    title: "Users",
    singular: "user",
    breadcrumb: "Administration",
    description:
      "Review team access and roles. Invite staff through organisation settings.",
    defaultSort: "display_name",
    columns: [
      {
        key: "display_name",
        label: "Team member",
        render: (item) => item.display_name || item.email,
        sortable: true,
      },
      {
        key: "role",
        label: "Role",
        render: (item) => roleName(item.role),
        sortable: true,
      },
    ],
    filters: [
      { key: "display_name", label: "Display name", type: "text" },
      { key: "email", label: "Email", type: "text" },
      {
        key: "role",
        label: "Role",
        type: "enum",
        options: roles.map((role) => ({ value: role.slug, label: role.name })),
        quick: true,
      },
    ],
    lifecycle: { activeLabel: "Active", archivedLabel: "Disabled" },
    actions: allowed
      ? [
          { key: "disable", label: "Disable access", danger: true },
          { key: "enable", label: "Enable access" },
        ]
      : [],
    getTitle: (item) => item.display_name || item.email,
    getSubtitle: (item) => item.email,
    canEdit: (item) => !item.is_disabled,
  };
  if (!allowed)
    return (
      <InlineNotification
        kind="error"
        title="Forbidden"
        subtitle="You do not have permission to manage users."
        hideCloseButton
      />
    );
  return (
    <>
      {metadata?.identity === identity && metadata.error && (
        <InlineNotification
          kind="error"
          title="Could not load edit options"
          subtitle={metadata.error}
          hideCloseButton
          lowContrast
        />
      )}
      <RecordWorkspace
        adapter={adapter}
        refreshKey={refreshKey}
        headerActions={<Button href="/organisation">Invite staff</Button>}
        onEdit={(item) => {
          setEditing(item);
          setError(null);
          setForm({
            display_name: item.display_name,
            role: item.role,
            default_location_id: item.default_location_id ?? "",
          });
        }}
        renderDetails={(item) => (
          <RecordDetails>
            <RecordDetail label="Email">{item.email}</RecordDetail>
            <RecordDetail label="Display name">
              {item.display_name}
            </RecordDetail>
            <RecordDetail label="Role">{roleName(item.role)}</RecordDetail>
            <RecordDetail label="Team">{item.team.name}</RecordDetail>
            <RecordDetail label="Default location">
              {locations.find(
                (location) => location.id === item.default_location_id,
              )?.name ??
                (item.default_location_id ? "Archived location" : "No default")}
            </RecordDetail>
            <RecordDetail label="Status">
              {item.is_disabled ? "Disabled" : "Active"}
            </RecordDetail>
          </RecordDetails>
        )}
      />
      <Modal
        open={editing !== null}
        modalHeading="Edit user"
        primaryButtonText={busy ? "Saving…" : "Save user"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={busy || !roles.length}
        onRequestClose={() => {
          if (!busy) setEditing(null);
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
            id="user-name"
            disabled={busy}
            labelText="Display name"
            value={form.display_name}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                display_name: event.target.value,
              }))
            }
          />
          <Select
            id="user-role"
            disabled={busy}
            labelText="Role"
            value={form.role}
            onChange={(event) =>
              setForm((current) => ({ ...current, role: event.target.value }))
            }
          >
            {roles.map((role) => (
              <SelectItem key={role.slug} value={role.slug} text={role.name} />
            ))}
          </Select>
          <Select
            id="user-location"
            disabled={busy}
            labelText="Default location"
            value={form.default_location_id}
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                default_location_id: event.target.value,
              }))
            }
          >
            <SelectItem value="" text="No default" />
            {editing?.default_location_id &&
              !locations.some(
                (location) => location.id === editing.default_location_id,
              ) && (
                <SelectItem
                  value={editing.default_location_id}
                  text="Current archived location"
                />
              )}
            {locations.map((location) => (
              <SelectItem
                key={location.id}
                value={location.id}
                text={`${location.name} (${location.type})`}
              />
            ))}
          </Select>
        </Stack>
      </Modal>
    </>
  );
}

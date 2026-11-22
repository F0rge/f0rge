"use client";
import {
  Button,
  InlineNotification,
  Modal,
  Select,
  SelectItem,
  Stack,
  Tab,
  TabList,
  TabPanel,
  TabPanels,
  Tabs,
  TextInput,
} from "@carbon/react";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { LocationBinsPanel } from "@/components/location-bins-panel";
import {
  RecordDetail,
  RecordDetails,
  RecordWorkspace,
  type RecordWorkspaceAdapter,
} from "@/components/record-workspace";
import {
  LOCATION_TYPES,
  canManageLocations,
  createLocation,
  updateLocation,
  type CreateLocationPayload,
  type Location,
  type LocationType,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { queryKeys } from "@/lib/queries";
import { workspaceIdentity } from "@/lib/record-workspace";

export default function LocationsPage() {
  const { user } = useAuth();
  return <LocationsScreen key={workspaceIdentity(user)} />;
}
function LocationsScreen() {
  const { user } = useAuth();
  const allowed = canManageLocations(user);
  const client = useQueryClient();
  const [refreshKey, setRefreshKey] = useState(0);
  // Editors cache locations; a write here refreshes them too.
  const refresh = () => {
    setRefreshKey((value) => value + 1);
    void client.invalidateQueries({ queryKey: queryKeys.locations });
  };
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Location | null>(null);
  const [bins, setBins] = useState<Location | null>(null);
  const [form, setForm] = useState<CreateLocationPayload>({
    name: "",
    type: "warehouse",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const close = () => {
    setCreating(false);
    setEditing(null);
    setError(null);
  };
  async function save() {
    setBusy(true);
    setError(null);
    try {
      if (editing) await updateLocation(editing.id, { name: form.name.trim() });
      else await createLocation({ ...form, name: form.name.trim() });
      close();
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save location.");
    } finally {
      setBusy(false);
    }
  }
  const adapter: RecordWorkspaceAdapter<Location> = {
    resource: "locations",
    title: "Locations",
    singular: "location",
    breadcrumb: "Catalogue management",
    description:
      "Review warehouses, showrooms and their bins, then manage location details.",
    columns: [
      {
        key: "name",
        label: "Location",
        render: (item) => item.name,
        sortable: true,
      },
      {
        key: "type",
        label: "Type",
        render: (item) =>
          LOCATION_TYPES.find((type) => type.value === item.type)?.label ??
          item.type,
        sortable: true,
      },
    ],
    filters: [
      { key: "name", label: "Name", type: "text" },
      {
        key: "type",
        label: "Type",
        type: "enum",
        options: LOCATION_TYPES,
        quick: true,
      },
    ],
    lifecycle: { activeLabel: "Active", archivedLabel: "Archived" },
    actions: allowed
      ? [
          { key: "archive", label: "Archive" },
          { key: "restore", label: "Restore" },
        ]
      : [],
    getTitle: (item) => item.name,
    getSubtitle: (item) =>
      item.type === "warehouse" ? "Warehouse" : "Showroom",
    canEdit: (item) => !item.is_archived,
  };
  return (
    <>
      <RecordWorkspace
        adapter={adapter}
        refreshKey={refreshKey}
        onCreate={
          allowed
            ? () => {
                setForm({ name: "", type: "warehouse" });
                setCreating(true);
              }
            : undefined
        }
        onEdit={
          allowed
            ? (item) => {
                setForm({ name: item.name, type: item.type });
                setEditing(item);
              }
            : undefined
        }
        renderDetails={(item) => (
          <Tabs>
            <TabList aria-label="Location information">
              <Tab>Overview</Tab>
              <Tab>Bins</Tab>
            </TabList>
            <TabPanels>
              <TabPanel>
                <RecordDetails>
                  <RecordDetail label="Name">{item.name}</RecordDetail>
                  <RecordDetail label="Type">{item.type}</RecordDetail>
                  <RecordDetail label="Status">
                    {item.is_archived ? "Archived" : "Active"}
                  </RecordDetail>
                </RecordDetails>
              </TabPanel>
              <TabPanel>
                <p>
                  View bins, generate a grid and print labels for this location.
                </p>
                <Button kind="tertiary" onClick={() => setBins(item)}>
                  {allowed ? "Manage bins" : "View bins"}
                </Button>
              </TabPanel>
            </TabPanels>
          </Tabs>
        )}
      />
      <Modal
        open={creating || editing !== null}
        modalHeading={editing ? "Rename location" : "Add location"}
        primaryButtonText={busy ? "Saving…" : "Save location"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={busy || !form.name.trim()}
        onRequestClose={() => {
          if (!busy) close();
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
            id="location-name"
            disabled={busy}
            labelText="Name"
            value={form.name}
            onChange={(event) =>
              setForm((current) => ({ ...current, name: event.target.value }))
            }
            required
          />
          {!editing && (
            <Select
              id="location-type"
            disabled={busy}
              labelText="Type"
              value={form.type}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  type: event.target.value as LocationType,
                }))
              }
            >
              {LOCATION_TYPES.map((type) => (
                <SelectItem
                  key={type.value}
                  value={type.value}
                  text={type.label}
                />
              ))}
            </Select>
          )}
        </Stack>
      </Modal>
      <Modal
        open={bins !== null}
        passiveModal
        modalHeading={bins ? `Bins at ${bins.name}` : "Location bins"}
        onRequestClose={() => setBins(null)}
        size="lg"
      >
        {bins && (
          <LocationBinsPanel
            key={bins.id}
            location={bins}
            canMutate={allowed && !bins.is_archived}
          />
        )}
      </Modal>
    </>
  );
}

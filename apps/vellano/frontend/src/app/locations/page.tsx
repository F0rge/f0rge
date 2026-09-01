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
import { Fragment, useCallback, useEffect, useState } from "react";

import { LocationBinsPanel } from "@/components/location-bins-panel";
import {
  LOCATION_TYPES,
  canManageLocations,
  createLocation,
  listLocations,
  updateLocation,
  type CreateLocationPayload,
  type Location,
  type LocationType,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "name", header: "Name" },
  { key: "type", header: "Type" },
  { key: "status", header: "Status" },
  { key: "actions", header: "Actions" },
] as const;

type LocationRow = {
  id: string;
  name: string;
  type: string;
  status: string;
  actions: string;
};

const emptyCreateForm: CreateLocationPayload = {
  name: "",
  type: "warehouse",
};

function locationTypeLabel(type: LocationType): string {
  return LOCATION_TYPES.find((entry) => entry.value === type)?.label ?? type;
}

export default function LocationsPage() {
  const { user } = useAuth();
  const canMutate = canManageLocations(user);
  const [locations, setLocations] = useState<Location[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [renameLocation, setRenameLocation] = useState<Location | null>(null);
  const [archiveLocation, setArchiveLocation] = useState<Location | null>(null);
  const [createForm, setCreateForm] = useState<CreateLocationPayload>(emptyCreateForm);
  const [renameName, setRenameName] = useState("");
  const [saving, setSaving] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const loadLocations = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listLocations();
      setLocations(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load locations.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadLocations();
    }
  }, [user, loadLocations]);

  const rows: LocationRow[] = locations.map((entry) => ({
    id: entry.id,
    name: entry.name,
    type: locationTypeLabel(entry.type),
    status: entry.is_archived ? "Archived" : "Active",
    actions: entry.id,
  }));

  function openRename(entry: Location) {
    setRenameLocation(entry);
    setRenameName(entry.name);
  }

  async function handleCreate() {
    setSaving(true);
    setError(null);
    try {
      await createLocation(createForm);
      setCreateOpen(false);
      setCreateForm(emptyCreateForm);
      await loadLocations();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create location.");
    } finally {
      setSaving(false);
    }
  }

  async function handleRename() {
    if (!renameLocation) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await updateLocation(renameLocation.id, { name: renameName });
      setRenameLocation(null);
      await loadLocations();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to rename location.");
    } finally {
      setSaving(false);
    }
  }

  async function handleArchive() {
    if (!archiveLocation) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await updateLocation(archiveLocation.id, { is_archived: true });
      setArchiveLocation(null);
      await loadLocations();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to archive location.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Stack gap={6}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="cds--type-productive-heading-04">Locations</h1>
          <p className="cds--type-body-01">
            Warehouses and showrooms used for stock, till, and receiving.
          </p>
        </div>
        {canMutate ? (
          <Button onClick={() => setCreateOpen(true)}>Add location</Button>
        ) : null}
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
        <p className="cds--type-body-01">Loading locations…</p>
      ) : locations.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No locations"
          subtitle="No locations have been configured yet."
          hideCloseButton
          lowContrast
        />
      ) : (
        <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
          {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Locations" description="All Vellano stock locations">
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
                    const entry = locations.find((loc) => loc.id === row.id);
                    const isExpanded = expandedId === row.id;
                    return (
                      <Fragment key={row.id}>
                        <TableRow {...getRowProps({ row })}>
                          {row.cells.map((cell) => {
                            if (cell.info.header === "actions") {
                              return (
                                <TableCell key={cell.id}>
                                  <Stack gap={3} orientation="horizontal">
                                    <Button
                                      kind="ghost"
                                      size="sm"
                                      onClick={() => setExpandedId(isExpanded ? null : row.id)}
                                    >
                                      {isExpanded ? "Hide bins" : "Bins"}
                                    </Button>
                                    {entry && canMutate ? (
                                      <>
                                        <Button
                                          kind="ghost"
                                          size="sm"
                                          disabled={saving}
                                          onClick={() => openRename(entry)}
                                        >
                                          Rename
                                        </Button>
                                        {!entry.is_archived ? (
                                          <Button
                                            kind="danger--ghost"
                                            size="sm"
                                            disabled={saving}
                                            onClick={() => setArchiveLocation(entry)}
                                          >
                                            Archive
                                          </Button>
                                        ) : null}
                                      </>
                                    ) : null}
                                  </Stack>
                                </TableCell>
                              );
                            }
                            return <TableCell key={cell.id}>{cell.value}</TableCell>;
                          })}
                        </TableRow>
                        {isExpanded && entry ? (
                          <TableRow>
                            <TableCell colSpan={TABLE_HEADERS.length}>
                              <LocationBinsPanel location={entry} canMutate={canMutate} />
                            </TableCell>
                          </TableRow>
                        ) : null}
                      </Fragment>
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
        modalHeading="Add location"
        primaryButtonText={saving ? "Adding…" : "Add"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || !createForm.name.trim()}
        onRequestClose={() => setCreateOpen(false)}
        onRequestSubmit={() => void handleCreate()}
      >
        <Stack gap={5}>
          <TextInput
            id="create-location-name"
            labelText="Name"
            value={createForm.name}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, name: event.target.value }))
            }
            required
          />
          <Select
            id="create-location-type"
            labelText="Type"
            value={createForm.type}
            onChange={(event) =>
              setCreateForm((form) => ({
                ...form,
                type: event.target.value as LocationType,
              }))
            }
          >
            {LOCATION_TYPES.map((type) => (
              <SelectItem key={type.value} value={type.value} text={type.label} />
            ))}
          </Select>
        </Stack>
      </Modal>

      <Modal
        open={renameLocation !== null}
        modalHeading="Rename location"
        primaryButtonText={saving ? "Saving…" : "Save"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || !renameName.trim()}
        onRequestClose={() => setRenameLocation(null)}
        onRequestSubmit={() => void handleRename()}
      >
        <TextInput
          id="rename-location-name"
          labelText="Name"
          value={renameName}
          onChange={(event) => setRenameName(event.target.value)}
        />
      </Modal>

      <Modal
        open={archiveLocation !== null}
        modalHeading="Archive location"
        primaryButtonText={saving ? "Archiving…" : "Archive"}
        secondaryButtonText="Cancel"
        danger
        primaryButtonDisabled={saving}
        onRequestClose={() => setArchiveLocation(null)}
        onRequestSubmit={() => void handleArchive()}
      >
        <p className="cds--type-body-01">
          Archive <strong>{archiveLocation?.name}</strong>? Archived locations stay visible but
          cannot be selected for new stock movements.
        </p>
      </Modal>
    </Stack>
  );
}

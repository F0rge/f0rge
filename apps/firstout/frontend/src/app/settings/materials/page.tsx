"use client";

import { Add } from "@carbon/icons-react";
import {
  Button, DataTableSkeleton, InlineNotification, Modal, OverflowMenu, OverflowMenuItem, Select, SelectItem, Stack,
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow, Tag, TextInput,
} from "@carbon/react";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { AdminPageHeader } from "@/components/administration";
import { useMaterials } from "@/components/catalogue-lists/hooks";
import { PageLoading } from "@/components/page-loading";
import { ApiError, can } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { groupMaterials } from "@/lib/catalogue-list-view";
import {
  MATERIAL_FAMILY_LABELS, createMaterial, updateMaterial, type ListLifecycle, type Material, type MaterialFamily,
} from "@/lib/catalogue-lists";
import { queryKeys } from "@/lib/queries";
import styles from "../../users/users.module.css";
import own from "../catalogue-lists.module.css";

const message = (error: unknown, fallback: string) => (error instanceof ApiError ? error.message : fallback);
const FAMILIES = Object.keys(MATERIAL_FAMILY_LABELS) as MaterialFamily[];

function MaterialModal({
  material, onClose, onSaved,
}: { material: Material | null; onClose: () => void; onSaved: (saved: Material) => void }) {
  const [name, setName] = useState(material?.name ?? "");
  const [family, setFamily] = useState<MaterialFamily | "">(material?.family ?? "");
  const [tried, setTried] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const nameError = !name.trim() ? "Enter a name." : "";
  const familyError = !family ? "Choose a family." : "";

  async function save() {
    setTried(true);
    if (nameError || familyError || !family || saving) return;
    setSaving(true);
    setError("");
    try {
      onSaved(material
        ? await updateMaterial(material.id, { name: name.trim(), family })
        : await createMaterial({ name: name.trim(), family }));
    } catch (err) {
      setError(message(err, "Could not save the material."));
      setSaving(false);
    }
  }

  return (
    <Modal
      open
      size="sm"
      modalHeading={material ? `Edit ${material.name}` : "Add material"}
      primaryButtonText={saving ? "Saving…" : "Save"}
      secondaryButtonText="Cancel"
      primaryButtonDisabled={saving}
      onRequestSubmit={() => void save()}
      onRequestClose={onClose}
    >
      <Stack gap={5}>
        {error && <InlineNotification lowContrast kind="error" title="Not saved" subtitle={error} hideCloseButton />}
        <TextInput id="material-name" labelText="Name" value={name} maxLength={64} data-modal-primary-focus
          invalid={tried && !!nameError} invalidText={nameError} onChange={(event) => setName(event.target.value)} />
        <Select id="material-family" labelText="Family" value={family} invalid={tried && !!familyError}
          invalidText={familyError} onChange={(event) => setFamily(event.target.value as MaterialFamily)}>
          <SelectItem value="" text="Choose a family" disabled />
          {FAMILIES.map((value) => <SelectItem key={value} value={value} text={MATERIAL_FAMILY_LABELS[value]} />)}
        </Select>
      </Stack>
    </Modal>
  );
}

function MaterialsScreen({ canMutate }: { canMutate: boolean }) {
  const [view, setView] = useState<ListLifecycle>("active");
  const [editing, setEditing] = useState<Material | "new" | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const client = useQueryClient();
  const list = useMaterials(view);
  const materials = list.data ?? null;
  // Every row this view returned, archived ones included.
  const groups = materials ? groupMaterials(materials, materials.map((material) => material.id)) : [];
  const loadError = list.error && !list.isFetching ? message(list.error, "Could not load materials.") : "";

  const refresh = () => Promise.all([
    client.invalidateQueries({ queryKey: ["materials"] }),
    client.invalidateQueries({ queryKey: queryKeys.skus }),
  ]);

  async function setArchived(material: Material, archived: boolean) {
    setError("");
    setNotice("");
    try {
      const saved = await updateMaterial(material.id, { is_archived: archived });
      setNotice(archived
        ? saved.sku_count
          ? `${saved.name} archived. ${saved.sku_count} active ${saved.sku_count === 1 ? "SKU keeps" : "SKUs keep"} it, but it can't be chosen for others.`
          : `${saved.name} archived.`
        : `${saved.name} restored.`);
      await refresh();
    } catch (err) {
      setError(message(err, `Could not change ${material.name}.`));
    }
  }

  return (
    <Stack gap={5} className={styles.page}>
      <AdminPageHeader
        title="Materials"
        description="What SKUs are made of. Each SKU has one main material and any number of others; the colour name and main material together make its finish."
      >
        {canMutate && <Button renderIcon={Add} onClick={() => setEditing("new")}>Add material</Button>}
      </AdminPageHeader>
      {!canMutate && (
        <InlineNotification lowContrast hideCloseButton kind="info" title="View only"
          subtitle="Changing materials needs the “Edit the catalogue” permission." />
      )}
      {notice && <InlineNotification lowContrast kind="success" title={notice} onCloseButtonClick={() => setNotice("")} />}
      {error && <InlineNotification lowContrast kind="error" title="Not changed" subtitle={error} onCloseButtonClick={() => setError("")} />}
      <section aria-labelledby="materials-title" className={styles.directory}>
        <h2 id="materials-title" className={styles.sectionTitle}>Materials by family</h2>
        <div className={styles.controls}>
          <div role="group" aria-label="Material status" className={styles.actions}>
            {([["active", "Active"], ["archived", "Archived"], ["all", "All"]] as const).map(([value, label]) => (
              <Button key={value} size="sm" kind={view === value ? "tertiary" : "ghost"} aria-pressed={view === value}
                onClick={() => setView(value)}>{label}</Button>
            ))}
          </div>
          {materials && <p role="status">{materials.length} {materials.length === 1 ? "material" : "materials"}</p>}
        </div>
        {loadError ? (
          <div className={styles.feedback}>
            <InlineNotification lowContrast kind="error" title="Could not load materials" subtitle={loadError} hideCloseButton />
            <Button size="sm" kind="tertiary" onClick={() => void list.refetch()}>Retry</Button>
          </div>
        ) : !materials ? (
          <DataTableSkeleton aria-label="Loading materials" columnCount={3} rowCount={5} showHeader={false} showToolbar={false} />
        ) : groups.length === 0 ? (
          <p role="status" className={styles.empty}>
            {view === "archived" ? "No archived materials." : "No materials yet."}
          </p>
        ) : (
          groups.map((group) => (
            <div key={group.family}>
              <h3 id={`family-${group.family}`} className={own.family}>{group.label}</h3>
              <div className={styles.tableScroll}>
                <Table size="md" aria-labelledby={`family-${group.family}`}>
                  <TableHead>
                    <TableRow>
                      <TableHeader>Name</TableHeader>
                      <TableHeader>SKUs</TableHeader>
                      <TableHeader>Status</TableHeader>
                      {canMutate && <TableHeader><span className="cds--visually-hidden">Actions</span></TableHeader>}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {group.materials.map((material) => (
                      <TableRow key={material.id}>
                        <TableCell>{material.name}</TableCell>
                        <TableCell>{material.sku_count}</TableCell>
                        <TableCell>
                          <Tag size="sm" type={material.is_archived ? "gray" : "green"}>
                            {material.is_archived ? "Archived" : "Active"}
                          </Tag>
                        </TableCell>
                        {canMutate && (
                          <TableCell>
                            <OverflowMenu aria-label={`Actions for ${material.name}`} iconDescription={`Actions for ${material.name}`} flipped size="sm">
                              <OverflowMenuItem itemText="Rename or change family" onClick={() => setEditing(material)} />
                              {material.is_archived ? (
                                <OverflowMenuItem itemText="Restore" onClick={() => void setArchived(material, false)} />
                              ) : (
                                <OverflowMenuItem itemText="Archive" hasDivider isDelete onClick={() => void setArchived(material, true)} />
                              )}
                            </OverflowMenu>
                          </TableCell>
                        )}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          ))
        )}
      </section>
      <p className="cds--type-helper-text-01">
        Archived materials stay on the SKUs that already have them but can&apos;t be chosen for new ones.
      </p>
      {editing && (
        <MaterialModal
          key={editing === "new" ? "new" : editing.id}
          material={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={(saved) => {
            setEditing(null);
            setNotice(editing === "new" ? `${saved.name} added to ${MATERIAL_FAMILY_LABELS[saved.family]}.` : `${saved.name} saved.`);
            void refresh();
          }}
        />
      )}
    </Stack>
  );
}

export default function MaterialsPage() {
  const { user, loading } = useAuth();
  if (loading) return <PageLoading label="Loading materials…" />;
  if (!user) return null;
  return <MaterialsScreen canMutate={can(user, "catalogue.mutate")} />;
}

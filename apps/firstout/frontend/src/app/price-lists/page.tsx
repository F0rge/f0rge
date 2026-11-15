"use client";

import { Button, ComboBox, InlineNotification, Modal, NumberInput, Stack, TextInput } from "@carbon/react";
import { useEffect, useState } from "react";
import { RecordDetail, RecordDetails, RecordWorkspace, type RecordWorkspaceAdapter } from "@/components/record-workspace";
import {
  canMutateCatalogue, createPriceList, deletePriceListItem, formatPriceAmount,
  listSkus, updatePriceList, upsertPriceListItem, type PriceList, type Sku,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { workspaceIdentity } from "@/lib/record-workspace";
import { PriceListItems } from "./price-list-items";
import styles from "./price-lists.module.css";

function skuLabel(item: Sku | null): string {
  return item ? `${item.our_ref} — ${item.name}` : "";
}

export default function PriceListsPage() {
  const { user } = useAuth();
  return <PriceListsContent key={workspaceIdentity(user)} />;
}

function PriceListsContent() {
  const { user } = useAuth();
  const canMutate = canMutateCatalogue(user);
  const [refreshKey, setRefreshKey] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createName, setCreateName] = useState("");
  const [editing, setEditing] = useState<PriceList | null>(null);
  const [detailName, setDetailName] = useState("");
  const [skus, setSkus] = useState<Sku[]>([]);
  const [skuId, setSkuId] = useState("");
  const [unitExVat, setUnitExVat] = useState<number | "">("");
  const [saving, setSaving] = useState(false);
  const [itemBusy, setItemBusy] = useState(false);
  const editingId = editing?.id;

  useEffect(() => {
    if (!editingId || !canMutate) return;
    let cancelled = false;
    void listSkus().then((items) => { if (!cancelled) setSkus(items); })
      .catch((err: unknown) => { if (!cancelled) setError(err instanceof Error ? err.message : "Could not load products."); });
    return () => { cancelled = true; };
  }, [editingId, canMutate]);

  const adapter: RecordWorkspaceAdapter<PriceList> = {
    resource: "price-lists", title: "Price lists", singular: "price list", breadcrumb: "Catalogue management",
    description: "Review customer price overrides and maintain SKU prices.",
    lifecycle: { activeLabel: "Active", archivedLabel: "Archived" }, defaultSort: "name",
    columns: [
      { key: "name", label: "Price list", render: (item) => item.name, sortable: true },
      { key: "item_count", label: "Prices", render: (item) => item.items.length, numeric: true, sortable: false },
    ],
    filters: [{ key: "name", label: "Name", type: "text" }],
    actions: canMutate ? [{ key: "archive", label: "Archive" }, { key: "restore", label: "Restore" }, { key: "delete", label: "Delete", danger: true }] : [],
    getTitle: (item) => item.name, getSubtitle: (item) => `${item.items.length} SKU prices · ex VAT`,
    canEdit: (item) => canMutate && !item.is_archived,
  };

  function openEdit(item: PriceList) {
    setEditing(item); setDetailName(item.name); setSkuId(""); setUnitExVat(""); setError(null);
  }

  function acceptUpdate(item: PriceList) {
    setEditing(item); setDetailName(item.name); setRefreshKey((value) => value + 1);
  }

  async function handleCreate() {
    if (!createName.trim()) return;
    setSaving(true); setError(null);
    try {
      await createPriceList({ name: createName.trim() });
      setCreateOpen(false); setCreateName(""); setRefreshKey((value) => value + 1);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not create price list."); }
    finally { setSaving(false); }
  }

  async function handleRename() {
    if (!editing || !detailName.trim()) return;
    setSaving(true); setError(null);
    try { acceptUpdate(await updatePriceList(editing.id, { name: detailName.trim() })); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not rename price list."); }
    finally { setSaving(false); }
  }

  async function handleUpsertItem() {
    if (!editing || !skuId || typeof unitExVat !== "number" || unitExVat <= 0) return;
    setItemBusy(true); setError(null);
    try {
      acceptUpdate(await upsertPriceListItem(editing.id, { sku_id: skuId, unit_ex_vat: formatPriceAmount(unitExVat) }));
      setSkuId(""); setUnitExVat("");
    } catch (err) { setError(err instanceof Error ? err.message : "Could not save price."); }
    finally { setItemBusy(false); }
  }

  async function handleDeleteItem(skuIdToRemove: string) {
    if (!editing) return;
    setItemBusy(true); setError(null);
    try { acceptUpdate(await deletePriceListItem(editing.id, skuIdToRemove)); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not remove price."); }
    finally { setItemBusy(false); }
  }

  const busy = saving || itemBusy;
  return <Stack gap={6}>
    {error && !createOpen && !editing && <InlineNotification kind="error" title="Price list action failed" subtitle={error} onCloseButtonClick={() => setError(null)} lowContrast />}
    <RecordWorkspace adapter={adapter} refreshKey={refreshKey}
      onCreate={canMutate ? () => { setError(null); setCreateOpen(true); } : undefined}
      onEdit={canMutate ? openEdit : undefined}
      renderDetails={(item) => <Stack gap={5}>
        <RecordDetails><RecordDetail label="Status">{item.is_archived ? "Archived" : "Active"}</RecordDetail><RecordDetail label="Prices">{item.items.length}</RecordDetail><RecordDetail label="VAT basis">Prices exclude VAT</RecordDetail></RecordDetails>
        <p className="cds--type-body-01">A list you create overrides the customer&apos;s classification. Cin7 lists do not.</p>
        <PriceListItems list={item} />
      </Stack>}
    />
    <Modal open={createOpen} modalHeading="New price list"
      primaryButtonText={saving ? "Creating…" : "Create"} secondaryButtonText="Cancel"
      primaryButtonDisabled={saving || !createName.trim()}
      onRequestClose={() => { if (!saving) setCreateOpen(false); }} onRequestSubmit={() => void handleCreate()}>
      <Stack gap={5}>{error && <InlineNotification kind="error" title="Could not create price list" subtitle={error} hideCloseButton lowContrast />}
        <TextInput id="create-price-list-name" labelText="Name" value={createName} disabled={saving} onChange={(event) => setCreateName(event.target.value)} required />
      </Stack>
    </Modal>
    <Modal open={editing !== null} modalHeading={editing ? `Edit ${editing.name}` : "Edit price list"} passiveModal
      onRequestClose={() => { if (!busy) setEditing(null); }} size="lg">
      {editing && <Stack gap={6}>
        {error && <InlineNotification kind="error" title="Could not save price list" subtitle={error} hideCloseButton lowContrast />}
        <TextInput id="price-list-rename" labelText="Name" value={detailName} disabled={busy} onChange={(event) => setDetailName(event.target.value)} />
        <div className={styles.editorActions}><Button kind="secondary" disabled={busy || !detailName.trim() || detailName.trim() === editing.name} onClick={() => void handleRename()}>{saving ? "Saving…" : "Save name"}</Button></div>
        <PriceListItems list={editing} busy={busy} onRemove={(id) => void handleDeleteItem(id)} />
        <h3 className="cds--type-heading-compact-01">Add or update price</h3>
        <ComboBox id="price-list-sku" titleText="SKU" placeholder="Type to search…" items={skus} itemToString={skuLabel}
          shouldFilterItem={({ item, itemToString, inputValue }) => !inputValue || (itemToString?.(item) ?? skuLabel(item)).toLowerCase().includes(inputValue.toLowerCase())}
          selectedItem={skus.find((item) => item.id === skuId) ?? null}
          onChange={({ selectedItem }) => setSkuId(selectedItem?.id ?? "")} disabled={busy} />
        <NumberInput id="price-list-unit-ex-vat" label="Unit ex VAT (ZAR)" min={0} step={0.01} allowEmpty value={unitExVat}
          onChange={(_, { value }) => setUnitExVat(value === "" ? "" : Number(value))} disabled={busy} />
        <Button disabled={busy || !skuId || typeof unitExVat !== "number" || unitExVat <= 0} onClick={() => void handleUpsertItem()}>{itemBusy ? "Saving…" : "Add / update price"}</Button>
        <Button kind="tertiary" disabled={busy} onClick={() => setEditing(null)}>Done</Button>
      </Stack>}
    </Modal>
  </Stack>;
}

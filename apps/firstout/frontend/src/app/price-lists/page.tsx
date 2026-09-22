// Superdesign skipped — out of credits (API generation blocked)
"use client";

import {
  Button,
  ComboBox,
  DataTable,
  InlineNotification,
  Modal,
  NumberInput,
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
import { TrashCan } from "@carbon/icons-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  canMutateCatalogue,
  createPriceList,
  deletePriceList,
  deletePriceListItem,
  formatPriceAmount,
  formatZarAmount,
  listPriceLists,
  listSkus,
  updatePriceList,
  upsertPriceListItem,
  type PriceList,
  type Sku,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "name", header: "Name" },
  { key: "item_count", header: "Items" },
] as const;

type PriceListRow = {
  id: string;
  name: string;
  item_count: string;
};

function skuItemToString(item: Sku | null): string {
  if (!item) {
    return "";
  }
  return `${item.our_ref} — ${item.name}`;
}

function shouldFilterSku({
  item,
  itemToString,
  inputValue,
}: {
  item: Sku;
  itemToString?: (item: Sku | null) => string;
  inputValue: string | null;
}): boolean {
  if (!inputValue) {
    return true;
  }
  const haystack = (itemToString ?? skuItemToString)(item).toLowerCase();
  return haystack.includes(inputValue.toLowerCase());
}

export default function PriceListsPage() {
  const { user } = useAuth();
  const canMutate = canMutateCatalogue(user);
  const [priceLists, setPriceLists] = useState<PriceList[]>([]);
  const [skus, setSkus] = useState<Sku[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createName, setCreateName] = useState("");
  const [selected, setSelected] = useState<PriceList | null>(null);
  const [detailName, setDetailName] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<PriceList | null>(null);
  const [skuId, setSkuId] = useState("");
  const [unitExVat, setUnitExVat] = useState<number | "">("");
  const [saving, setSaving] = useState(false);
  const [itemBusy, setItemBusy] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [lists, catalogue] = await Promise.all([listPriceLists(), listSkus()]);
      setPriceLists(lists);
      setSkus(catalogue);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load price lists.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadData();
    }
  }, [user, loadData]);

  const rows: PriceListRow[] = priceLists.map((entry) => ({
    id: entry.id,
    name: entry.name,
    item_count: String(entry.items.length),
  }));

  const skuOptions = useMemo(() => skus, [skus]);
  const selectedSku = skuOptions.find((entry) => entry.id === skuId) ?? null;

  function openDetail(entry: PriceList) {
    setSelected(entry);
    setDetailName(entry.name);
    setSkuId("");
    setUnitExVat("");
  }

  function closeDetail() {
    setSelected(null);
    setDetailName("");
    setSkuId("");
    setUnitExVat("");
  }

  async function handleCreate() {
    setSaving(true);
    setError(null);
    try {
      await createPriceList({ name: createName.trim() });
      setCreateOpen(false);
      setCreateName("");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create price list.");
    } finally {
      setSaving(false);
    }
  }

  async function handleRename() {
    if (!selected || !detailName.trim()) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const updated = await updatePriceList(selected.id, { name: detailName.trim() });
      setSelected(updated);
      setDetailName(updated.name);
      setPriceLists((current) =>
        current.map((entry) => (entry.id === updated.id ? updated : entry)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to rename price list.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDeleteList() {
    if (!deleteTarget) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await deletePriceList(deleteTarget.id);
      if (selected?.id === deleteTarget.id) {
        closeDetail();
      }
      setDeleteTarget(null);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete price list.");
    } finally {
      setSaving(false);
    }
  }

  async function handleUpsertItem() {
    if (!selected || !skuId) {
      return;
    }
    if (typeof unitExVat !== "number" || unitExVat <= 0) {
      setError("Unit ex VAT must be greater than zero.");
      return;
    }
    setItemBusy(true);
    setError(null);
    try {
      const updated = await upsertPriceListItem(selected.id, {
        sku_id: skuId,
        unit_ex_vat: formatPriceAmount(unitExVat),
      });
      setSelected(updated);
      setPriceLists((current) =>
        current.map((entry) => (entry.id === updated.id ? updated : entry)),
      );
      setSkuId("");
      setUnitExVat("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save item.");
    } finally {
      setItemBusy(false);
    }
  }

  async function handleDeleteItem(sku_id: string) {
    if (!selected) {
      return;
    }
    setItemBusy(true);
    setError(null);
    try {
      const updated = await deletePriceListItem(selected.id, sku_id);
      setSelected(updated);
      setPriceLists((current) =>
        current.map((entry) => (entry.id === updated.id ? updated : entry)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove item.");
    } finally {
      setItemBusy(false);
    }
  }

  const canAddItem =
    canMutate && Boolean(skuId) && typeof unitExVat === "number" && unitExVat > 0;

  return (
    <Stack gap={6}>
      <div className="firstout-page-header">
        <div>
          <h1 className="cds--type-productive-heading-04">Price lists</h1>
          <p className="cds--type-body-01">
            Named SKU price lists for trade customers. Resolves before wholesale and retail.
          </p>
        </div>
        {canMutate ? (
          <Button onClick={() => setCreateOpen(true)}>New price list</Button>
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
        <p className="cds--type-body-01">Loading price lists…</p>
      ) : priceLists.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No price lists"
          subtitle="No named price lists have been created yet."
          hideCloseButton
          lowContrast
        />
      ) : (
        <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
          {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Price lists" description="Click a row to manage items">
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
                    const entry = priceLists.find((list) => list.id === row.id);
                    return (
                      <TableRow
                        {...getRowProps({ row })}
                        key={row.id}
                        style={{ cursor: entry ? "pointer" : undefined }}
                        onClick={() => {
                          if (entry) {
                            openDetail(entry);
                          }
                        }}
                      >
                        {row.cells.map((cell) => (
                          <TableCell key={cell.id}>{cell.value}</TableCell>
                        ))}
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
        modalHeading="New price list"
        primaryButtonText={saving ? "Creating…" : "Create"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || !createName.trim()}
        onRequestClose={() => setCreateOpen(false)}
        onRequestSubmit={() => void handleCreate()}
      >
        <TextInput
          id="create-price-list-name"
          labelText="Name"
          value={createName}
          onChange={(event) => setCreateName(event.target.value)}
          required
        />
      </Modal>

      <Modal
        open={selected !== null}
        modalHeading={selected?.name ?? "Price list"}
        passiveModal
        onRequestClose={closeDetail}
      >
        {selected ? (
          <Stack gap={6}>
            {canMutate ? (
              <Stack gap={5}>
                <TextInput
                  id="price-list-rename"
                  labelText="Name"
                  value={detailName}
                  onChange={(event) => setDetailName(event.target.value)}
                />
                <div style={{ display: "flex", gap: "0.75rem" }}>
                  <Button
                    kind="secondary"
                    disabled={saving || !detailName.trim() || detailName.trim() === selected.name}
                    onClick={() => void handleRename()}
                  >
                    {saving ? "Saving…" : "Save name"}
                  </Button>
                  <Button kind="danger--tertiary" onClick={() => setDeleteTarget(selected)}>
                    Delete list
                  </Button>
                </div>
              </Stack>
            ) : null}

            <TableContainer title="Items" description="SKU unit prices ex VAT">
              <Table size="sm">
                <TableHead>
                  <TableRow>
                    <TableHeader>Our ref</TableHeader>
                    <TableHeader>Unit ex VAT</TableHeader>
                    {canMutate ? <TableHeader /> : null}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {selected.items.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={canMutate ? 3 : 2}>No items yet.</TableCell>
                    </TableRow>
                  ) : (
                    selected.items.map((item) => (
                      <TableRow key={item.sku_id}>
                        <TableCell>{item.our_ref}</TableCell>
                        <TableCell>{formatZarAmount(item.unit_ex_vat)}</TableCell>
                        {canMutate ? (
                          <TableCell>
                            <Button
                              kind="ghost"
                              size="sm"
                              renderIcon={TrashCan}
                              iconDescription="Remove item"
                              hasIconOnly
                              disabled={itemBusy}
                              onClick={() => void handleDeleteItem(item.sku_id)}
                            />
                          </TableCell>
                        ) : null}
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </TableContainer>

            {canMutate ? (
              <Stack gap={5}>
                <h3 className="cds--type-productive-heading-02">Add or update item</h3>
                <ComboBox
                  id="price-list-sku"
                  titleText="SKU"
                  placeholder="Type to search…"
                  items={skuOptions}
                  itemToString={skuItemToString}
                  shouldFilterItem={shouldFilterSku}
                  selectedItem={selectedSku}
                  onChange={({ selectedItem: picked }) => setSkuId(picked?.id ?? "")}
                  disabled={itemBusy}
                />
                <NumberInput
                  id="price-list-unit-ex-vat"
                  label="Unit ex VAT (ZAR)"
                  min={0}
                  step={0.01}
                  allowEmpty
                  value={unitExVat}
                  onChange={(_event, { value }) => {
                    setUnitExVat(value === "" ? "" : Number(value));
                  }}
                  disabled={itemBusy}
                />
                <Button disabled={!canAddItem || itemBusy} onClick={() => void handleUpsertItem()}>
                  {itemBusy ? "Saving…" : "Add / update item"}
                </Button>
              </Stack>
            ) : null}
          </Stack>
        ) : null}
      </Modal>

      <Modal
        open={deleteTarget !== null}
        modalHeading="Delete price list"
        danger
        primaryButtonText={saving ? "Deleting…" : "Delete"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving}
        onRequestClose={() => setDeleteTarget(null)}
        onRequestSubmit={() => void handleDeleteList()}
      >
        <p className="cds--type-body-01">
          Delete {deleteTarget?.name}? Customers assigned to this list will have their assignment
          cleared.
        </p>
      </Modal>
    </Stack>
  );
}

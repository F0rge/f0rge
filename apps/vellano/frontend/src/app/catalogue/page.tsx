"use client";

import {
  Button,
  Checkbox,
  DataTable,
  FileUploaderDropContainer,
  FileUploaderItem,
  InlineNotification,
  Modal,
  NumberInput,
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
import { Barcode, DocumentImport, Printer } from "@carbon/icons-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";

import { SkuPriceEditor } from "@/components/sku-price-editor";
import {
  ApiError,
  canMutateCatalogue,
  canViewCostAudit,
  createSku,
  formatPriceAmount,
  formatZarAmount,
  isActiveLocation,
  listInventory,
  listLocations,
  listSkus,
  parsePriceInput,
  uploadSkuPhoto,
  type CreateSkuPayload,
  type Location,
  type Sku,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

const TABLE_HEADERS = [
  { key: "select", header: "" },
  { key: "product", header: "SKU / Product Name" },
  { key: "category", header: "Category" },
  { key: "preferred_supplier", header: "Preferred supplier" },
  { key: "lead_time_days", header: "Lead time" },
  { key: "reorder_min", header: "Reorder min" },
  { key: "cost_zar", header: "Cost (ZAR)" },
  { key: "retail_inc_vat", header: "Retail Price" },
  { key: "wholesale_inc_vat", header: "Trade Price" },
  { key: "our_barcode", header: "Our barcode" },
  { key: "actions", header: "Actions" },
] as const;

type SkuRow = {
  id: string;
  product: string;
  category: string;
  preferred_supplier: string;
  lead_time_days: string;
  reorder_min: string;
  cost_zar: string;
  retail_inc_vat: string;
  wholesale_inc_vat: string;
  our_barcode: string;
  select: string;
  actions: string;
};

function formatLeadTime(days: number | null | undefined): string {
  if (days === null || days === undefined) {
    return "—";
  }
  return `${days} days`;
}

const emptyCreateForm: CreateSkuPayload = {
  our_ref: "",
  our_barcode: "",
  name: "",
  design: "",
  fabric: "",
};

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function formatIncVatPrice(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }
  return formatZarAmount(formatPriceAmount(parsed));
}

function printSkuLabels(targetSkus: Sku[]): void {
  if (targetSkus.length === 0) {
    return;
  }
  const printWindow = window.open("", "_blank", "noopener,noreferrer");
  if (!printWindow) {
    return;
  }
  const labelsHtml = targetSkus
    .map(
      (sku) => `
    <div class="label">
      <div class="name">${escapeHtml(sku.name)}</div>
      <div class="ref">${escapeHtml(sku.our_ref)}</div>
      <div class="barcode">${escapeHtml(sku.our_barcode)}</div>
    </div>`,
    )
    .join("");
  printWindow.document.write(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Barcode labels</title>
  <style>
    body { font-family: "IBM Plex Sans", sans-serif; margin: 1.5rem; color: #161616; }
    .label { page-break-inside: avoid; margin-bottom: 2rem; padding: 1rem; border: 1px solid #e0e0e0; }
    .name { font-size: 1rem; margin-bottom: 0.25rem; }
    .ref { font-weight: 600; margin-bottom: 0.5rem; }
    .barcode { font-family: monospace; font-size: 1.75rem; font-weight: 600; letter-spacing: 0.05em; }
    @media print { body { margin: 0; } .label { border: none; } }
  </style>
</head>
<body>${labelsHtml}</body>
</html>`);
  printWindow.document.close();
  printWindow.focus();
  printWindow.print();
}

function CataloguePageContent() {
  const { user } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const canMutate = canMutateCatalogue(user?.role);
  const [skus, setSkus] = useState<Sku[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [unitCostBySku, setUnitCostBySku] = useState<Map<string, string>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [priceSku, setPriceSku] = useState<Sku | null>(null);
  const [createForm, setCreateForm] = useState<CreateSkuPayload>(emptyCreateForm);
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [recordStockNow, setRecordStockNow] = useState(false);
  const [openingLocationId, setOpeningLocationId] = useState("");
  const [openingQty, setOpeningQty] = useState<number | "">(1);
  const [openingUnitCost, setOpeningUnitCost] = useState("");
  const [openingDate, setOpeningDate] = useState("");
  const [saving, setSaving] = useState(false);
  const [searchFilter, setSearchFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set());

  const loadSkus = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [skuData, inventoryData] = await Promise.all([listSkus(), listInventory()]);
      setSkus(skuData);
      const costs = new Map<string, string>();
      for (const entry of inventoryData) {
        if (entry.unit_cost_zar) {
          costs.set(entry.sku_id, entry.unit_cost_zar);
        }
      }
      setUnitCostBySku(costs);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load catalogue.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) {
      void loadSkus();
    }
  }, [user, loadSkus]);

  useEffect(() => {
    if (!user || !canMutate) {
      return;
    }
    let cancelled = false;
    listLocations()
      .then((data) => {
        if (!cancelled) {
          setLocations(data.filter(isActiveLocation));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLocations([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [user, canMutate]);

  useEffect(() => {
    if (!canMutate || searchParams.get("new") !== "1") {
      return;
    }
    setCreateOpen(true);
    const next = new URLSearchParams(searchParams.toString());
    next.delete("new");
    const qs = next.toString();
    router.replace(qs ? `/catalogue?${qs}` : "/catalogue");
  }, [canMutate, searchParams, router]);

  const categories = useMemo(() => {
    const values = new Set<string>();
    for (const sku of skus) {
      const category = sku.category?.trim();
      if (category) {
        values.add(category);
      }
    }
    return Array.from(values).sort((a, b) => a.localeCompare(b));
  }, [skus]);

  const filteredSkus = useMemo(() => {
    const query = searchFilter.trim().toLowerCase();
    return skus.filter((sku) => {
      if (categoryFilter && sku.category?.trim() !== categoryFilter) {
        return false;
      }
      if (!query) {
        return true;
      }
      return (
        sku.name.toLowerCase().includes(query) ||
        sku.our_ref.toLowerCase().includes(query) ||
        sku.our_barcode.toLowerCase().includes(query)
      );
    });
  }, [skus, categoryFilter, searchFilter]);

  const allFilteredSelected =
    filteredSkus.length > 0 && filteredSkus.every((sku) => selectedIds.has(sku.id));

  const rows: SkuRow[] = filteredSkus.map((entry) => ({
    id: entry.id,
    product: entry.id,
    category: entry.category?.trim() || "—",
    preferred_supplier: entry.preferred_supplier_name?.trim() || "—",
    lead_time_days: formatLeadTime(entry.lead_time_days),
    reorder_min: entry.reorder_min !== null ? String(entry.reorder_min) : "—",
    cost_zar: formatZarAmount(unitCostBySku.get(entry.id) ?? null),
    retail_inc_vat: formatIncVatPrice(entry.retail_inc_vat),
    wholesale_inc_vat: formatIncVatPrice(entry.wholesale_inc_vat),
    our_barcode: entry.our_barcode,
    select: entry.id,
    actions: entry.id,
  }));

  function resetForm() {
    setCreateForm(emptyCreateForm);
    setPhotoFile(null);
    setRecordStockNow(false);
    setOpeningLocationId("");
    setOpeningQty(1);
    setOpeningUnitCost("");
    setOpeningDate("");
  }

  function openPriceEditor(entry: Sku) {
    setPriceSku(entry);
  }

  function toggleSelect(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function toggleSelectAllFiltered() {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (allFilteredSelected) {
        for (const sku of filteredSkus) {
          next.delete(sku.id);
        }
      } else {
        for (const sku of filteredSkus) {
          next.add(sku.id);
        }
      }
      return next;
    });
  }

  function handlePrintLabels() {
    const targetSkus =
      selectedIds.size > 0
        ? filteredSkus.filter((sku) => selectedIds.has(sku.id))
        : filteredSkus;
    printSkuLabels(targetSkus);
  }

  async function handleCreate() {
    setSaving(true);
    setError(null);
    try {
      const payload: CreateSkuPayload = {
        our_ref: createForm.our_ref.trim(),
        our_barcode: createForm.our_barcode.trim(),
        name: createForm.name.trim(),
        design: createForm.design.trim(),
        fabric: createForm.fabric.trim(),
      };
      const supplierRef = createForm.supplier_ref?.trim();
      if (supplierRef) {
        payload.supplier_ref = supplierRef;
      }
      const category = createForm.category?.trim();
      if (category) {
        payload.category = category;
      }
      if (recordStockNow) {
        const cost = parsePriceInput(openingUnitCost);
        if (!openingLocationId || openingQty === "" || cost === null) {
          setError("Location, quantity, and unit cost are required to record stock.");
          setSaving(false);
          return;
        }
        payload.opening_location_id = openingLocationId;
        payload.opening_qty = Number(openingQty);
        payload.opening_unit_cost_zar = formatPriceAmount(cost);
        const date = openingDate.trim();
        if (date) {
          payload.opening_date = date;
        }
      }
      const created = await createSku(payload);
      if (photoFile) {
        await uploadSkuPhoto(created.id, photoFile);
      }
      setCreateOpen(false);
      resetForm();
      await loadSkus();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Failed to add SKU.");
      }
    } finally {
      setSaving(false);
    }
  }

  const skuFieldsValid = Boolean(
    createForm.our_ref.trim() &&
      createForm.our_barcode.trim() &&
      createForm.name.trim() &&
      createForm.design.trim() &&
      createForm.fabric.trim(),
  );
  const parsedOpeningCost = parsePriceInput(openingUnitCost);
  const openingValid =
    !recordStockNow ||
    Boolean(
      openingLocationId &&
        typeof openingQty === "number" &&
        Number.isFinite(openingQty) &&
        openingQty >= 1 &&
        parsedOpeningCost !== null &&
        parsedOpeningCost > 0,
    );
  const formValid = skuFieldsValid && openingValid;

  return (
    <Stack gap={6}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 className="cds--type-productive-heading-04">Catalogue</h1>
          <p className="cds--type-body-01">
            Manage products, pricing tiers, and generate barcode labels.
          </p>
        </div>
        {canMutate ? (
          <div className="vellano-catalogue-actions">
            <Button
              kind="secondary"
              renderIcon={DocumentImport}
              onClick={() => router.push("/import")}
            >
              Import
            </Button>
            <Button onClick={() => setCreateOpen(true)}>Add SKU</Button>
          </div>
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

      <SkuPriceEditor
        sku={priceSku}
        open={priceSku !== null}
        readOnly={!canMutate}
        showCostAudit={canViewCostAudit(user?.role)}
        unitCostZar={priceSku ? (unitCostBySku.get(priceSku.id) ?? null) : null}
        saving={saving}
        onSavingChange={setSaving}
        onClose={() => setPriceSku(null)}
        onSaved={loadSkus}
        onError={setError}
      />

      {loading ? (
        <p className="cds--type-body-01">Loading catalogue…</p>
      ) : skus.length === 0 ? (
        <InlineNotification
          kind="info"
          title="No SKUs"
          subtitle="No catalogue items have been added yet."
          hideCloseButton
          lowContrast
        />
      ) : (
        <div className="vellano-catalogue-panel">
          <div className="vellano-catalogue-toolbar">
            <div className="vellano-catalogue-toolbar__left">
              <TextInput
                id="catalogue-search"
                labelText="Filter SKUs"
                hideLabel
                placeholder="Filter SKUs…"
                value={searchFilter}
                onChange={(event) => setSearchFilter(event.target.value)}
                size="md"
              />
              <div className="vellano-catalogue-toolbar__divider" aria-hidden />
              <div className="vellano-catalogue-chips" role="group" aria-label="Category filter">
                <Button
                  kind={categoryFilter === null ? "primary" : "ghost"}
                  size="sm"
                  onClick={() => setCategoryFilter(null)}
                >
                  All
                </Button>
                {categories.map((category) => (
                  <Button
                    key={category}
                    kind={categoryFilter === category ? "primary" : "ghost"}
                    size="sm"
                    onClick={() => setCategoryFilter(category)}
                  >
                    {category}
                  </Button>
                ))}
              </div>
            </div>
            <Button kind="ghost" renderIcon={Printer} onClick={handlePrintLabels}>
              Print labels
            </Button>
          </div>

          <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
            {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
              <TableContainer title="Catalogue" description="All Vellano SKUs">
                <Table {...getTableProps()}>
                  <TableHead>
                    <TableRow>
                      {headers.map((header) => (
                        <TableHeader {...getHeaderProps({ header })} key={header.key}>
                          {header.key === "select" ? (
                            <Checkbox
                              id="catalogue-select-all"
                              labelText="Select all"
                              hideLabel
                              checked={allFilteredSelected}
                              indeterminate={!allFilteredSelected && filteredSkus.some((sku) => selectedIds.has(sku.id))}
                              onChange={() => toggleSelectAllFiltered()}
                            />
                          ) : (
                            header.header
                          )}
                        </TableHeader>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {tableRows.length === 0 ? (
                      <TableRow>
                        <TableCell colSpan={headers.length}>
                          No SKUs match the current filters.
                        </TableCell>
                      </TableRow>
                    ) : (
                      tableRows.map((row) => {
                        const entry = filteredSkus.find((sku) => sku.id === row.id);
                        return (
                          <TableRow
                            {...getRowProps({
                              row,
                              onClick: () => {
                                if (entry) {
                                  openPriceEditor(entry);
                                }
                              },
                            })}
                            key={row.id}
                            style={{ cursor: entry ? "pointer" : undefined }}
                          >
                            {row.cells.map((cell) => {
                              if (cell.info.header === "select" && entry) {
                                return (
                                  <TableCell key={cell.id}>
                                    <Checkbox
                                      id={`catalogue-select-${entry.id}`}
                                      labelText={`Select ${entry.our_ref}`}
                                      hideLabel
                                      checked={selectedIds.has(entry.id)}
                                      onClick={(event) => event.stopPropagation()}
                                      onChange={() => toggleSelect(entry.id)}
                                    />
                                  </TableCell>
                                );
                              }
                              if (cell.info.header === "product" && entry) {
                                return (
                                  <TableCell key={cell.id}>
                                    <div className="cds--type-semibold">{entry.our_ref}</div>
                                    <div className="cds--type-caption-01">{entry.name}</div>
                                  </TableCell>
                                );
                              }
                              if (
                                cell.info.header === "cost_zar" ||
                                cell.info.header === "retail_inc_vat" ||
                                cell.info.header === "wholesale_inc_vat"
                              ) {
                                return (
                                  <TableCell key={cell.id} style={{ textAlign: "right" }}>
                                    {cell.value}
                                  </TableCell>
                                );
                              }
                              if (cell.info.header === "actions" && entry) {
                                return (
                                  <TableCell key={cell.id} style={{ textAlign: "center" }}>
                                    <Button
                                      type="button"
                                      kind="ghost"
                                      size="sm"
                                      hasIconOnly
                                      iconDescription="Print label"
                                      renderIcon={Barcode}
                                      onClick={(event) => {
                                        event.preventDefault();
                                        event.stopPropagation();
                                        printSkuLabels([entry]);
                                      }}
                                    />
                                    <Button
                                      type="button"
                                      kind="ghost"
                                      size="sm"
                                      onClick={(event) => {
                                        event.preventDefault();
                                        event.stopPropagation();
                                        openPriceEditor(entry);
                                      }}
                                    >
                                      {canMutate ? "Edit prices" : "View prices"}
                                    </Button>
                                  </TableCell>
                                );
                              }
                              return <TableCell key={cell.id}>{cell.value}</TableCell>;
                            })}
                          </TableRow>
                        );
                      })
                    )}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </DataTable>
        </div>
      )}

      <Modal
        open={createOpen}
        modalHeading="Add SKU"
        primaryButtonText={saving ? "Adding…" : "Add"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={saving || !formValid}
        onRequestClose={() => setCreateOpen(false)}
        onRequestSubmit={() => void handleCreate()}
        size="lg"
      >
        <Stack gap={5}>
          <TextInput
            id="create-sku-our-ref"
            labelText="Our ref"
            value={createForm.our_ref}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, our_ref: event.target.value }))
            }
            required
          />
          <TextInput
            id="create-sku-our-barcode"
            labelText="Our barcode"
            value={createForm.our_barcode}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, our_barcode: event.target.value }))
            }
            required
          />
          <TextInput
            id="create-sku-name"
            labelText="Name"
            value={createForm.name}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, name: event.target.value }))
            }
            required
          />
          <TextInput
            id="create-sku-category"
            labelText="Category"
            helperText="Optional — e.g. Seating, Tables"
            value={createForm.category ?? ""}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, category: event.target.value }))
            }
          />
          <TextInput
            id="create-sku-design"
            labelText="Design"
            value={createForm.design}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, design: event.target.value }))
            }
            required
          />
          <TextInput
            id="create-sku-fabric"
            labelText="Fabric"
            value={createForm.fabric}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, fabric: event.target.value }))
            }
            required
          />
          <TextInput
            id="create-sku-supplier-ref"
            labelText="Supplier ref"
            helperText="Supplier's reference — not our barcode"
            value={createForm.supplier_ref ?? ""}
            onChange={(event) =>
              setCreateForm((form) => ({ ...form, supplier_ref: event.target.value }))
            }
          />
          <div>
            <p className="cds--label">Photo (optional)</p>
            <FileUploaderDropContainer
              accept={["image/*"]}
              labelText="Drag and drop an image here or click to upload"
              multiple={false}
              onAddFiles={(_, { addedFiles }) => {
                const file = addedFiles[0];
                if (file && !file.invalidFileType) {
                  setPhotoFile(file);
                }
              }}
            />
            {photoFile ? (
              <FileUploaderItem
                name={photoFile.name}
                status="complete"
                onDelete={() => setPhotoFile(null)}
              />
            ) : null}
          </div>
          <Stack gap={4}>
            <div>
              <h2 className="cds--type-productive-heading-02">Initial Opening Stock (Optional)</h2>
              <p className="cds--type-body-01">Optional day-one stock without a PO.</p>
            </div>
            <Checkbox
              id="create-sku-record-stock"
              labelText="Record stock now"
              checked={recordStockNow}
              onChange={(_, { checked }) => setRecordStockNow(checked)}
            />
            {recordStockNow ? (
              <Stack gap={4}>
                <Select
                  id="create-sku-opening-location"
                  labelText="Location"
                  value={openingLocationId}
                  onChange={(event) => setOpeningLocationId(event.target.value)}
                  helperText={
                    locations.length === 0 ? "No active locations available" : undefined
                  }
                >
                  <SelectItem value="" text="Select location" />
                  {locations.map((entry) => (
                    <SelectItem key={entry.id} value={entry.id} text={entry.name} />
                  ))}
                </Select>
                <NumberInput
                  id="create-sku-opening-qty"
                  label="Quantity on Hand"
                  min={1}
                  step={1}
                  value={openingQty}
                  onChange={(_event, { value }) => {
                    if (value === "") {
                      setOpeningQty("");
                    } else {
                      setOpeningQty(Number(value));
                    }
                  }}
                />
                <TextInput
                  id="create-sku-opening-unit-cost"
                  labelText="Unit Cost (ZAR)"
                  helperText="Used for inventory valuation"
                  value={openingUnitCost}
                  onChange={(event) => setOpeningUnitCost(event.target.value)}
                />
                <TextInput
                  id="create-sku-opening-date"
                  labelText="Received Date"
                  type="date"
                  value={openingDate}
                  onChange={(event) => setOpeningDate(event.target.value)}
                />
              </Stack>
            ) : null}
          </Stack>
        </Stack>
      </Modal>
    </Stack>
  );
}

export default function CataloguePage() {
  return (
    <Suspense fallback={<p className="cds--type-body-01">Loading catalogue…</p>}>
      <CataloguePageContent />
    </Suspense>
  );
}

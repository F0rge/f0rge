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
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

import { SkuPriceEditor } from "@/components/sku-price-editor";
import {
  ApiError,
  canMutateCatalogue,
  createSku,
  displayPrice,
  formatPriceAmount,
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
  { key: "name", header: "Name" },
  { key: "actions", header: "Actions" },
  { key: "wholesale_ex_vat", header: "Wholesale ex-VAT" },
  { key: "wholesale_inc_vat", header: "Wholesale inc-VAT" },
  { key: "retail_ex_vat", header: "Retail ex-VAT" },
  { key: "retail_inc_vat", header: "Retail inc-VAT" },
  { key: "design", header: "Design" },
  { key: "fabric", header: "Fabric" },
  { key: "our_ref", header: "Our ref" },
  { key: "our_barcode", header: "Our barcode" },
  { key: "supplier_ref", header: "Supplier ref" },
  { key: "photo", header: "Photo" },
] as const;

type SkuRow = {
  id: string;
  name: string;
  design: string;
  fabric: string;
  our_ref: string;
  our_barcode: string;
  supplier_ref: string;
  wholesale_ex_vat: string;
  wholesale_inc_vat: string;
  retail_ex_vat: string;
  retail_inc_vat: string;
  photo: string;
  actions: string;
};

const emptyCreateForm: CreateSkuPayload = {
  our_ref: "",
  our_barcode: "",
  name: "",
  design: "",
  fabric: "",
  supplier_ref: "",
};

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

  const rows: SkuRow[] = skus.map((entry) => ({
    id: entry.id,
    name: entry.name,
    design: entry.design,
    fabric: entry.fabric,
    our_ref: entry.our_ref,
    our_barcode: entry.our_barcode,
    supplier_ref: entry.supplier_ref ?? "—",
    wholesale_ex_vat: displayPrice(entry.wholesale_ex_vat),
    wholesale_inc_vat: displayPrice(entry.wholesale_inc_vat),
    retail_ex_vat: displayPrice(entry.retail_ex_vat),
    retail_inc_vat: displayPrice(entry.retail_inc_vat),
    photo: entry.id,
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
            SKU catalogue — our refs and barcodes distinct from supplier references.
          </p>
        </div>
        {canMutate ? <Button onClick={() => setCreateOpen(true)}>Add SKU</Button> : null}
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
        <DataTable rows={rows} headers={[...TABLE_HEADERS]}>
          {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
            <TableContainer title="Catalogue" description="All Vellano SKUs">
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
                    const entry = skus.find((sku) => sku.id === row.id);
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
                          if (cell.info.header === "photo") {
                            if (entry?.photo_storage_key) {
                              return (
                                <TableCell key={cell.id}>
                                  {/* eslint-disable-next-line @next/next/no-img-element */}
                                  <img
                                    src={`/api/v1/skus/${entry.id}/photo`}
                                    alt={entry.name}
                                    style={{ maxHeight: "3rem", maxWidth: "3rem", objectFit: "cover" }}
                                  />
                                </TableCell>
                              );
                            }
                            return <TableCell key={cell.id}>—</TableCell>;
                          }
                          if (cell.info.header === "actions" && entry) {
                            return (
                              <TableCell key={cell.id}>
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
                  })}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </DataTable>
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

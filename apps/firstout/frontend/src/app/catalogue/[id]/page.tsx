"use client";

import {
  Button,
  FileUploaderDropContainer,
  FileUploaderItem,
  InlineNotification,
  Modal,
  NumberInput,
  Stack,
  Tab,
  TabList,
  TabPanel,
  TabPanels,
  Tabs,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Tag,
  TextInput,
  Tile,
} from "@carbon/react";
import { Barcode } from "@carbon/icons-react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { CostAuditPanel } from "@/components/cost-audit-panel";
import { SkuBomEditor } from "@/components/sku-bom-editor";
import { SkuPriceEditor } from "@/components/sku-price-editor";
import {
  ApiError,
  canMutateCatalogue,
  canViewCostAudit,
  deleteSku,
  formatZarAmount,
  getSku,
  getSkuLeadTimes,
  listInventory,
  listSkus,
  skuPhotoUrl,
  updateSku,
  uploadSkuPhoto,
  type InventorySku,
  type Sku,
  type SkuLeadTimeRow,
  type UpdateSkuPricePayload,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { isValidCartonCount, skuCartonCount } from "@/lib/carton-helpers";
import { formatObservedMedianLine, skuLeadTimeById } from "@/lib/lead-times";
import { printSkuLabels } from "@/lib/sku-label-print";
import { formatStockQty, visibleBins } from "@/lib/stock-table";

type SkuIdentityForm = {
  our_ref: string;
  our_barcode: string;
  name: string;
  design: string;
  fabric: string;
  category: string;
  carton_count: number | "";
};

function emptyIdentityForm(): SkuIdentityForm {
  return {
    our_ref: "",
    our_barcode: "",
    name: "",
    design: "",
    fabric: "",
    category: "",
    carton_count: 1,
  };
}

function identityFormFromSku(sku: Sku): SkuIdentityForm {
  return {
    our_ref: sku.our_ref,
    our_barcode: sku.our_barcode,
    name: sku.name,
    design: sku.design,
    fabric: sku.fabric,
    category: sku.category ?? "",
    carton_count: skuCartonCount(sku),
  };
}

function isIdentityFormValid(form: SkuIdentityForm): boolean {
  return (
    Boolean(
      form.our_ref.trim() &&
        form.our_barcode.trim() &&
        form.name.trim() &&
        form.design.trim() &&
        form.fabric.trim(),
    ) && isValidCartonCount(form.carton_count)
  );
}

export default function SkuDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const canMutate = canMutateCatalogue(user);
  const canViewCost = canViewCostAudit(user);
  const [sku, setSku] = useState<Sku | null>(null);
  const [inventoryRow, setInventoryRow] = useState<InventorySku | null>(null);
  const [allSkus, setAllSkus] = useState<Sku[]>([]);
  const [observedLeadTime, setObservedLeadTime] = useState<
    Pick<SkuLeadTimeRow, "median_days" | "n"> | null
  >(null);
  const [identityForm, setIdentityForm] = useState<SkuIdentityForm>(emptyIdentityForm);
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [identitySaving, setIdentitySaving] = useState(false);
  const [priceSaving, setPriceSaving] = useState(false);
  const [photoUploading, setPhotoUploading] = useState(false);
  const [deleteSaving, setDeleteSaving] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const loadSku = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [skuData, inventoryData, leadReport, catalogue] = await Promise.all([
        getSku(params.id),
        listInventory(),
        getSkuLeadTimes().catch(() => ({ rows: [] as SkuLeadTimeRow[] })),
        listSkus(),
      ]);
      setSku(skuData);
      setIdentityForm(identityFormFromSku(skuData));
      setInventoryRow(inventoryData.find((entry) => entry.sku_id === skuData.id) ?? null);
      setObservedLeadTime(skuLeadTimeById(leadReport.rows).get(skuData.id) ?? null);
      setAllSkus(catalogue);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load SKU.");
      setSku(null);
    } finally {
      setLoading(false);
    }
  }, [params.id]);

  useEffect(() => {
    if (user && params.id) {
      void loadSku();
    }
  }, [user, params.id, loadSku]);

  async function handleIdentitySave() {
    if (!sku || !canMutate || !isIdentityFormValid(identityForm)) {
      return;
    }
    setIdentitySaving(true);
    setError(null);
    setSuccess(null);
    try {
      const payload: UpdateSkuPricePayload = {
        our_ref: identityForm.our_ref.trim(),
        our_barcode: identityForm.our_barcode.trim(),
        name: identityForm.name.trim(),
        design: identityForm.design.trim(),
        fabric: identityForm.fabric.trim(),
        category: identityForm.category.trim() || null,
        carton_count:
          identityForm.carton_count === "" ? undefined : identityForm.carton_count,
      };
      const updated = await updateSku(sku.id, payload);
      setSku(updated);
      setIdentityForm(identityFormFromSku(updated));
      setSuccess("SKU identity saved.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Failed to update SKU.");
      }
    } finally {
      setIdentitySaving(false);
    }
  }

  async function handlePhotoUpload() {
    if (!sku || !photoFile || !canMutate || sku.photo_storage_key) {
      return;
    }
    setPhotoUploading(true);
    setError(null);
    setSuccess(null);
    try {
      const updated = await uploadSkuPhoto(sku.id, photoFile);
      setSku(updated);
      setPhotoFile(null);
      setSuccess("Photo uploaded.");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Failed to upload photo.");
      }
    } finally {
      setPhotoUploading(false);
    }
  }

  async function handleDelete() {
    if (!sku || !canMutate) {
      return;
    }
    setDeleteSaving(true);
    setError(null);
    try {
      await deleteSku(sku.id);
      router.push("/catalogue");
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Failed to delete SKU.");
      }
      setDeleteOpen(false);
    } finally {
      setDeleteSaving(false);
    }
  }

  const unitCostZar = inventoryRow?.unit_cost_zar ?? null;

  return (
    <Stack gap={6}>
      <div className="firstout-page-header">
        <div>
          <Button kind="ghost" size="sm" onClick={() => router.push("/catalogue")}>
            Back to catalogue
          </Button>
          <div style={{ display: "flex", alignItems: "flex-start", gap: "1rem", marginTop: "0.5rem" }}>
            {sku?.photo_storage_key ? (
              <img
                src={skuPhotoUrl(sku.id)}
                alt={sku.name}
                width={80}
                height={80}
                style={{ objectFit: "cover", flexShrink: 0 }}
              />
            ) : null}
            <div>
              <h1 className="cds--type-productive-heading-04">
                {sku ? `${sku.our_ref} — ${sku.name}` : "SKU"}
              </h1>
              {sku?.is_kit ? (
                <Tag type="teal" size="sm">
                  Kit
                </Tag>
              ) : null}
            </div>
          </div>
        </div>
        {sku ? (
          <div className="firstout-catalogue-actions">
            <Button
              kind="secondary"
              renderIcon={Barcode}
              onClick={() => printSkuLabels([sku])}
            >
              Print label
            </Button>
            {canMutate ? (
              <Button kind="danger--tertiary" onClick={() => setDeleteOpen(true)}>
                Delete
              </Button>
            ) : null}
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

      {success ? (
        <InlineNotification
          kind="success"
          title="Saved"
          subtitle={success}
          onCloseButtonClick={() => setSuccess(null)}
          lowContrast
        />
      ) : null}

      {loading ? (
        <p className="cds--type-body-01">Loading SKU…</p>
      ) : sku ? (
        <Tabs>
          <TabList aria-label="SKU detail">
            <Tab>Identity</Tab>
            <Tab>Prices</Tab>
            <Tab>Stock</Tab>
            {canViewCost ? <Tab>Cost</Tab> : null}
            <Tab>Kit</Tab>
          </TabList>
          <TabPanels>
            <TabPanel>
              <Tile>
                <Stack gap={5}>
                  <h2 className="cds--type-productive-heading-03">Identity</h2>
                  {canMutate && !sku.photo_storage_key ? (
                    <div>
                      <p className="cds--type-label-01">Product photo</p>
                      {photoFile ? (
                        <FileUploaderItem
                          name={photoFile.name}
                          status="edit"
                          onDelete={() => setPhotoFile(null)}
                        />
                      ) : (
                        <FileUploaderDropContainer
                          accept={["image/jpeg", "image/png", "image/webp"]}
                          labelText="Drag and drop a photo here or click to upload"
                          multiple={false}
                          onAddFiles={(_event, { addedFiles }) => {
                            const file = addedFiles[0];
                            if (file) {
                              setPhotoFile(file);
                            }
                          }}
                        />
                      )}
                      {photoFile ? (
                        <Button
                          kind="secondary"
                          size="sm"
                          disabled={photoUploading}
                          onClick={() => void handlePhotoUpload()}
                        >
                          {photoUploading ? "Uploading…" : "Upload photo"}
                        </Button>
                      ) : null}
                    </div>
                  ) : sku.photo_storage_key ? (
                    <img
                      src={skuPhotoUrl(sku.id)}
                      alt={sku.name}
                      width={160}
                      height={160}
                      style={{ objectFit: "cover" }}
                    />
                  ) : null}
                  <TextInput
                    id="detail-sku-our-ref"
                    labelText="Our ref *"
                    value={identityForm.our_ref}
                    readOnly={!canMutate}
                    onChange={(event) =>
                      setIdentityForm((form) => ({ ...form, our_ref: event.target.value }))
                    }
                  />
                  <TextInput
                    id="detail-sku-our-barcode"
                    labelText="Our barcode *"
                    value={identityForm.our_barcode}
                    readOnly={!canMutate}
                    onChange={(event) =>
                      setIdentityForm((form) => ({ ...form, our_barcode: event.target.value }))
                    }
                  />
                  <TextInput
                    id="detail-sku-name"
                    labelText="Name *"
                    value={identityForm.name}
                    readOnly={!canMutate}
                    onChange={(event) =>
                      setIdentityForm((form) => ({ ...form, name: event.target.value }))
                    }
                  />
                  <TextInput
                    id="detail-sku-design"
                    labelText="Design *"
                    value={identityForm.design}
                    readOnly={!canMutate}
                    onChange={(event) =>
                      setIdentityForm((form) => ({ ...form, design: event.target.value }))
                    }
                  />
                  <TextInput
                    id="detail-sku-fabric"
                    labelText="Fabric *"
                    value={identityForm.fabric}
                    readOnly={!canMutate}
                    onChange={(event) =>
                      setIdentityForm((form) => ({ ...form, fabric: event.target.value }))
                    }
                  />
                  <TextInput
                    id="detail-sku-category"
                    labelText="Category"
                    value={identityForm.category}
                    readOnly={!canMutate}
                    onChange={(event) =>
                      setIdentityForm((form) => ({ ...form, category: event.target.value }))
                    }
                  />
                  <NumberInput
                    id="detail-sku-carton-count"
                    label="Cartons"
                    helperText="Sellable unit ships in this many cartons. Default 1. Not a kit BOM."
                    min={1}
                    step={1}
                    allowEmpty
                    readOnly={!canMutate}
                    value={identityForm.carton_count}
                    invalid={
                      identityForm.carton_count !== "" && !isValidCartonCount(identityForm.carton_count)
                    }
                    invalidText="Cartons must be 1 or more"
                    onChange={(_event, { value }) => {
                      setIdentityForm((form) => ({
                        ...form,
                        carton_count: value === "" ? "" : Number(value),
                      }));
                    }}
                  />
                  {canMutate ? (
                    <Button
                      kind="primary"
                      disabled={identitySaving || !isIdentityFormValid(identityForm)}
                      onClick={() => void handleIdentitySave()}
                    >
                      {identitySaving ? "Saving…" : "Save identity"}
                    </Button>
                  ) : null}
                </Stack>
              </Tile>
            </TabPanel>
            <TabPanel>
              <Tile>
                <SkuPriceEditor
                  sku={sku}
                  open
                  embedded
                  readOnly={!canMutate}
                  showCostAudit={false}
                  unitCostZar={unitCostZar}
                  observedLeadTime={observedLeadTime}
                  saving={priceSaving}
                  onSavingChange={setPriceSaving}
                  onClose={() => {}}
                  onSaved={loadSku}
                  onError={setError}
                />
              </Tile>
            </TabPanel>
            <TabPanel>
              <Tile>
                <Stack gap={5}>
                  <h2 className="cds--type-productive-heading-03">Stock</h2>
                  {!inventoryRow ? (
                    <p className="cds--type-body-01">No on-hand or on-order yet.</p>
                  ) : (
                    <>
                      <div className="firstout-detail-grid">
                        <div>
                          <div className="cds--label">On hand</div>
                          <p className="cds--type-body-01">{formatStockQty(inventoryRow.on_hand)}</p>
                        </div>
                        <div>
                          <div className="cds--label">On order</div>
                          <p className="cds--type-body-01">{formatStockQty(inventoryRow.on_order)}</p>
                        </div>
                        {canViewCost ? (
                          <div>
                            <div className="cds--label">Unit cost</div>
                            <p className="cds--type-body-01">
                              {formatZarAmount(inventoryRow.unit_cost_zar)}
                            </p>
                          </div>
                        ) : null}
                      </div>
                      {inventoryRow.locations.length > 0 ? (
                        <Table size="sm">
                          <TableHead>
                            <TableRow>
                              <TableHeader>Location</TableHeader>
                              <TableHeader>On hand</TableHeader>
                              {canViewCost ? <TableHeader>Unit cost</TableHeader> : null}
                              <TableHeader>Bins</TableHeader>
                            </TableRow>
                          </TableHead>
                          <TableBody>
                            {inventoryRow.locations.map((location) => {
                              const bins = visibleBins(location.bins);
                              return (
                                <TableRow key={location.location_id}>
                                  <TableCell>{location.location_name}</TableCell>
                                  <TableCell>{formatStockQty(location.on_hand)}</TableCell>
                                  {canViewCost ? (
                                    <TableCell>{formatZarAmount(location.unit_cost_zar)}</TableCell>
                                  ) : null}
                                  <TableCell>
                                    {bins.length > 0
                                      ? bins
                                          .map((bin) => `${bin.code}: ${bin.on_hand}`)
                                          .join(" · ")
                                      : "—"}
                                  </TableCell>
                                </TableRow>
                              );
                            })}
                          </TableBody>
                        </Table>
                      ) : (
                        <p className="cds--type-body-01">No location breakdown yet.</p>
                      )}
                    </>
                  )}
                </Stack>
              </Tile>
            </TabPanel>
            {canViewCost ? (
              <TabPanel>
                <Tile>
                  <Stack gap={5}>
                    <h2 className="cds--type-productive-heading-03">Cost history</h2>
                    {sku.last_landed_cost_zar ? (
                      <p className="cds--type-body-01">
                        Last landed cost: {formatZarAmount(sku.last_landed_cost_zar)}
                      </p>
                    ) : null}
                    {observedLeadTime ? (
                      <p className="cds--type-caption-01">
                        Observed median lead time: {formatObservedMedianLine(observedLeadTime)}
                      </p>
                    ) : null}
                    <CostAuditPanel pinnedSkuId={sku.id} />
                  </Stack>
                </Tile>
              </TabPanel>
            ) : null}
            <TabPanel>
              <SkuBomEditor
                sku={sku}
                skus={allSkus}
                open
                variant="section"
                canMutate={canMutate}
                onClose={() => {}}
                onSaved={loadSku}
                onError={setError}
              />
            </TabPanel>
          </TabPanels>
        </Tabs>
      ) : (
        <InlineNotification
          kind="error"
          title="Not found"
          subtitle="This SKU could not be loaded."
          hideCloseButton
          lowContrast
        />
      )}

      <Modal
        open={deleteOpen}
        modalHeading="Delete SKU"
        primaryButtonText={deleteSaving ? "Deleting…" : "Delete"}
        secondaryButtonText="Cancel"
        danger
        primaryButtonDisabled={deleteSaving}
        onRequestClose={() => setDeleteOpen(false)}
        onRequestSubmit={() => void handleDelete()}
      >
        <p className="cds--type-body-01">
          Delete <strong>{sku?.our_ref}</strong> ({sku?.name})? This cannot be undone.
        </p>
      </Modal>
    </Stack>
  );
}

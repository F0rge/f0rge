"use client";

import { LoadingField, LoadingRegion } from "@/components/page-loading";
import { StaffImage } from "@/components/staff-image";
import { SkuProductDetailsFields } from "@/components/sku-product-details-fields";
import { skuDetailsFormFromSku, skuDetailsPayload, validateSkuDetails, type SkuDetailsForm } from "@/lib/sku-details";

import {
  Button,
  FileUploaderDropContainer,
  FileUploaderItem,
  InlineNotification,
  NumberInput,
  SkeletonPlaceholder,
  SkeletonText,
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
  Toggle,
} from "@carbon/react";
import { Barcode } from "@carbon/icons-react";
import { useParams, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";

import { WorkspaceBulkDialog } from "@/components/record-workspace/workspace-bulk-dialog";
import { CostAuditPanel } from "@/components/cost-audit-panel";
import { SkuBomEditor } from "@/components/sku-bom-editor";
import { SkuPriceEditor } from "@/components/sku-price-editor";
import {
  ApiError,
  canMutateCatalogue,
  canViewCostAudit,
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
import { queryKeys } from "@/lib/queries";
import { isValidCartonCount, skuCartonCount } from "@/lib/carton-helpers";
import { formatObservedMedianLine, skuLeadTimeById } from "@/lib/lead-times";
import { canToggleShopVisibility, SHOP_HIDDEN_HELP, setSkuShopHidden } from "@/lib/shop-visibility";
import { printSkuLabels } from "@/lib/sku-label-print";
import { formatStockQty, visibleBins } from "@/lib/stock-table";

type SkuIdentityForm = SkuDetailsForm & {
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
    ...skuDetailsFormFromSku({}),
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
    ...skuDetailsFormFromSku(sku),
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
    ) && isValidCartonCount(form.carton_count) && !Object.keys(validateSkuDetails(form)).length
  );
}

export default function SkuDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const allowed = canMutateCatalogue(user);
  const canViewCost = canViewCostAudit(user);
  const [sku, setSku] = useState<Sku | null>(null);
  const canMutate = allowed && !sku?.is_archived;
  const [inventoryRow, setInventoryRow] = useState<InventorySku | null>(null);
  const [allSkus, setAllSkus] = useState<Sku[]>([]);
  const [observedLeadTime, setObservedLeadTime] = useState<
    Pick<SkuLeadTimeRow, "median_days" | "n"> | null
  >(null);
  const [identityForm, setIdentityForm] = useState<SkuIdentityForm>(emptyIdentityForm);
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailTab, setDetailTab] = useState(0);
  const [identitySaving, setIdentitySaving] = useState(false);
  const [shopSaving, setShopSaving] = useState(false);
  const [photoUploading, setPhotoUploading] = useState(false);
  const [lifecycleAction, setLifecycleAction] = useState<"archive" | "restore" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const client = useQueryClient();
  // Editors elsewhere price against the shared SKU list; a write here makes it stale.
  const skusChanged = () => {
    void client.invalidateQueries({ queryKey: queryKeys.skus });
    void client.invalidateQueries({ queryKey: ["sku-cost-audit"] });
  };

  const loadSku = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [skuData, inventoryData, leadReport, catalogue] = await Promise.all([
        getSku(params.id),
        listInventory(),
        getSkuLeadTimes().catch(() => ({ rows: [] as SkuLeadTimeRow[] })),
        listSkus({ lifecycle: "all" }),
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
        ...skuDetailsPayload(identityForm, sku),
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
      skusChanged();
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

  async function handleShopHiddenChange(hidden: boolean) {
    if (!sku || !canToggleShopVisibility(user, sku)) {
      return;
    }
    setShopSaving(true);
    setError(null);
    setSuccess(null);
    try {
      setSku(await setSkuShopHidden(sku.id, hidden));
      skusChanged();
      setSuccess(hidden ? "Hidden from the shop." : "No longer hidden from the shop.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update shop visibility.");
    } finally {
      setShopSaving(false);
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
      skusChanged();
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

  if (loading || (sku !== null && sku.id !== params.id)) {
    return (
      <Stack gap={6} className="firstout-loading-motion">
        <div>
          <Button kind="ghost" size="sm" onClick={() => router.push("/catalogue")}>Back to catalogue</Button>
          <SkeletonText heading width="min(28rem, 85%)" />
        </div>
        <LoadingRegion label="Loading SKU…">
          <Tabs selectedIndex={0}>
            <TabList aria-label="SKU detail">
              <Tab>Identity</Tab>
              <Tab disabled>Prices</Tab>
              <Tab disabled>Stock</Tab>
              {canViewCost ? <Tab disabled>Cost</Tab> : null}
              <Tab disabled>Kit</Tab>
            </TabList>
            <TabPanels>
              <TabPanel>
                <Tile>
                  <Stack gap={5}>
                    <h2 className="cds--type-productive-heading-03">Identity</h2>
                    <div aria-hidden="true"><SkeletonPlaceholder style={{ inlineSize: "10rem", blockSize: "10rem" }} /></div>
                    {["Our ref *", "Our barcode *", "Name *", "Design *", "Fabric *", "Category", "Cartons"].map((field) => (
                      <LoadingField key={field} label={field} />
                    ))}
                  </Stack>
                </Tile>
              </TabPanel>
              <TabPanel />
              <TabPanel />
              {canViewCost ? <TabPanel /> : null}
              <TabPanel />
            </TabPanels>
          </Tabs>
        </LoadingRegion>
      </Stack>
    );
  }

  return (
    <Stack gap={6}>
      <div className="firstout-page-header">
        <div>
          <Button kind="ghost" size="sm" onClick={() => router.push("/catalogue")}>
            Back to catalogue
          </Button>
          <div style={{ display: "flex", alignItems: "flex-start", gap: "1rem", marginTop: "0.5rem" }}>
            {sku?.photo_storage_key ? (
              <StaffImage
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
              {sku?.is_archived && <Tag type="gray" size="sm">Archived</Tag>}
              {sku?.is_kit ? (
                <Tag type="teal" size="sm">
                  Kit
                </Tag>
              ) : null}
              {sku && !sku.is_sellable ? (
                <Tag type="gray" size="sm">
                  Not for sale
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
            {allowed ? (
              <Button kind="tertiary" onClick={() => setLifecycleAction(sku.is_archived ? "restore" : "archive")}>
                {sku.is_archived ? "Restore SKU" : "Archive SKU"}
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>

      {sku?.is_archived && <InlineNotification
        kind="info"
        title="Archived SKU — restore before editing"
        subtitle="Stock and past records are kept. Existing commitments, returns and stock corrections remain available. This kit recipe is read-only while archived. Restoring keeps the previous sales setting and does not republish online."
        lowContrast hideCloseButton
      />}

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

      {sku ? (
        <Tabs selectedIndex={detailTab} onChange={({ selectedIndex }) => setDetailTab(selectedIndex)}>
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
                    <div role="group" aria-label="Product photos" style={{ display: "flex", flexWrap: "wrap", gap: "1rem" }}>
                      {Array.from({ length: sku.gallery_photo_count || 1 }, (_, index) => (
                        <StaffImage
                          key={index}
                          src={skuPhotoUrl(sku.id, sku.gallery_photo_count ? index + 1 : undefined)}
                          alt={`${sku.name}, ${index ? `alternate view ${index}` : "main photo"}`}
                          width={160}
                          height={160}
                          style={{ objectFit: "contain" }}
                        />
                      ))}
                    </div>
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
                  <SkuProductDetailsFields
                    idPrefix="detail-sku"
                    form={identityForm}
                    errors={validateSkuDetails(identityForm)}
                    readOnly={!canMutate}
                    disabled={identitySaving}
                    onChange={(field, value) => setIdentityForm((form) => ({ ...form, [field]: value }))}
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
                  {canToggleShopVisibility(user, sku) ? (
                    <div>
                      <Toggle
                        id="detail-sku-storefront-hidden"
                        labelText="Hide from shop"
                        labelA="Off"
                        labelB="On"
                        toggled={sku.storefront_hidden ?? false}
                        disabled={shopSaving}
                        onToggle={(checked) => void handleShopHiddenChange(checked)}
                      />
                      <p className="cds--type-helper-text-01">{SHOP_HIDDEN_HELP}</p>
                    </div>
                  ) : null}
                </Stack>
              </Tile>
            </TabPanel>
            <TabPanel>
              <Tile>
                <SkuPriceEditor
                  key={sku.id}
                  sku={sku}
                  active={detailTab === 1}
                  readOnly={!canMutate}
                  canViewCost={canViewCost}
                  observedLeadTime={observedLeadTime}
                  onSaved={(updated) => {
                    setSku(updated);
                    skusChanged();
                    setSuccess("SKU changes saved.");
                  }}
                  onError={(message) => {
                    setError(message);
                    setSuccess(null);
                  }}
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
                onSaved={async () => { skusChanged(); await loadSku(); }}
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

      {lifecycleAction && sku && allowed && (
        <WorkspaceBulkDialog
          resource="skus"
          operation={{ action: lifecycleAction, label: lifecycleAction === "restore" ? "Restore" : "Archive", count: 1, selection: { ids: [sku.id] } }}
          fields={[]}
          onClose={() => setLifecycleAction(null)}
          onComplete={(message) => { setSuccess(message); skusChanged(); void loadSku(); }}
        />
      )}
    </Stack>
  );
}

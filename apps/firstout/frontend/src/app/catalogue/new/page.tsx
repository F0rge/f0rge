"use client";

import {
  Button,
  Checkbox,
  Column,
  FileUploaderDropContainer,
  FileUploaderItem,
  Grid,
  InlineNotification,
  NumberInput,
  Select,
  SelectItem,
  Stack,
  TextInput,
  Tile,
} from "@carbon/react";
import { ArrowLeft, Save } from "@carbon/icons-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  ApiError,
  canMutateCatalogue,
  createSku,
  formatPriceAmount,
  isActiveLocation,
  listLocations,
  parsePriceInput,
  updateSku,
  uploadSkuPhoto,
  type CreateSkuPayload,
  type Location,
  type UpdateSkuPricePayload,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { isValidCartonCount } from "@/lib/carton-helpers";
import {
  SKU_PHOTO_ACCEPT,
  missingNewSkuFields,
  missingNewSkuMessage,
  pickSkuPhoto,
} from "@/lib/new-sku-form";

const emptyCreateForm: CreateSkuPayload = {
  our_ref: "",
  our_barcode: "",
  name: "",
  design: "",
  fabric: "",
};

function parseOptionalIncVat(value: string, label: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = parsePriceInput(trimmed);
  if (parsed === null) {
    throw new Error(`${label} must be a number.`);
  }
  return formatPriceAmount(parsed);
}

export default function NewSkuPage() {
  const { user } = useAuth();
  const router = useRouter();
  const canMutate = canMutateCatalogue(user);
  const [createForm, setCreateForm] = useState<CreateSkuPayload>(emptyCreateForm);
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoPreviewUrl, setPhotoPreviewUrl] = useState<string | null>(null);
  const [photoError, setPhotoError] = useState<string | null>(null);
  const [stockistIncVat, setStockistIncVat] = useState("");
  const [wholesaleIncVat, setWholesaleIncVat] = useState("");
  const [decoratorIncVat, setDecoratorIncVat] = useState("");
  const [retailIncVat, setRetailIncVat] = useState("");
  const [recordStockNow, setRecordStockNow] = useState(false);
  const [openingLocationId, setOpeningLocationId] = useState("");
  const [openingQty, setOpeningQty] = useState<number | "">(1);
  const [openingUnitCost, setOpeningUnitCost] = useState("");
  const [openingDate, setOpeningDate] = useState("");
  const [cartonCount, setCartonCount] = useState<number | "">(1);
  const [locations, setLocations] = useState<Location[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!canMutate) {
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
  }, [canMutate]);

  useEffect(() => {
    if (!photoFile) {
      setPhotoPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(photoFile);
    setPhotoPreviewUrl(url);
    return () => {
      URL.revokeObjectURL(url);
    };
  }, [photoFile]);

  const missingFields = missingNewSkuFields({
    ourRef: createForm.our_ref,
    name: createForm.name,
    design: createForm.design,
    fabric: createForm.fabric,
    cartonCount,
    recordStockNow,
    openingLocationId,
    openingQty,
    openingUnitCost,
  });
  const missingMessage = missingNewSkuMessage(missingFields);
  const missing = new Set(missingFields);
  const formValid = missingFields.length === 0;

  async function handleCreate() {
    if (!canMutate || !formValid) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const payload: CreateSkuPayload = {
        our_ref: createForm.our_ref.trim(),
        name: createForm.name.trim(),
        design: createForm.design.trim(),
        fabric: createForm.fabric.trim(),
      };
      const barcode = createForm.our_barcode?.trim() ?? "";
      if (barcode) {
        payload.our_barcode = barcode;
      }
      const supplierRef = createForm.supplier_ref?.trim();
      if (supplierRef) {
        payload.supplier_ref = supplierRef;
      }
      const category = createForm.category?.trim();
      if (category) {
        payload.category = category;
      }
      if (isValidCartonCount(cartonCount)) {
        payload.carton_count = cartonCount;
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

      const pricePayload: UpdateSkuPricePayload = {};
      const stockist = parseOptionalIncVat(stockistIncVat, "Stockist inc VAT");
      if (stockist !== null) {
        pricePayload.stockist_inc_vat = stockist;
      }
      const wholesale = parseOptionalIncVat(wholesaleIncVat, "Wholesale inc VAT");
      if (wholesale !== null) {
        pricePayload.wholesale_inc_vat = wholesale;
      }
      const decorator = parseOptionalIncVat(decoratorIncVat, "Decorator inc VAT");
      if (decorator !== null) {
        pricePayload.decorator_inc_vat = decorator;
      }
      const retail = parseOptionalIncVat(retailIncVat, "Retail inc VAT");
      if (retail !== null) {
        pricePayload.retail_inc_vat = retail;
      }
      if (Object.keys(pricePayload).length > 0) {
        await updateSku(created.id, pricePayload);
      }

      if (photoFile) {
        await uploadSkuPhoto(created.id, photoFile);
      }

      router.push(`/catalogue/${created.id}`);
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

  function goBack() {
    router.push("/catalogue");
  }

  if (!canMutate) {
    return (
      <section className="firstout-forbidden">
        <Stack gap={5}>
          <InlineNotification
            kind="error"
            title="Forbidden"
            subtitle="Only owner and buyer can create SKUs."
            hideCloseButton
          />
          <Button kind="secondary" renderIcon={ArrowLeft} onClick={goBack}>
            Back to catalogue
          </Button>
        </Stack>
      </section>
    );
  }

  return (
    <div className="firstout-sku-form">
      <Stack gap={6}>
      <div className="firstout-page-header">
        <div>
          <h1 className="cds--type-productive-heading-04">Create new SKU</h1>
          <p className="cds--type-body-01">
            Add a new item to catalogue and optional opening stock.
          </p>
        </div>
        <Button kind="ghost" renderIcon={ArrowLeft} onClick={goBack}>
          Back to catalogue
        </Button>
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

      <form
        onSubmit={(event) => {
          event.preventDefault();
          void handleCreate();
        }}
      >
        <Stack gap={5}>
          <Tile>
            <Stack gap={5}>
              <h2 className="cds--type-productive-heading-02">Item</h2>
              <Grid condensed fullWidth>
                <Column lg={8} md={4} sm={4}>
                  <TextInput
                    id="new-sku-our-ref"
                    labelText="Our ref *"
                    value={createForm.our_ref}
                    onChange={(event) =>
                      setCreateForm((form) => ({ ...form, our_ref: event.target.value }))
                    }
                    invalid={missing.has("Our ref")}
                    invalidText="Our ref is required"
                    required
                  />
                </Column>
                <Column lg={8} md={4} sm={4}>
                  <TextInput
                    id="new-sku-our-barcode"
                    labelText="Our barcode"
                    helperText="Optional. Not the supplier's reference. Leave blank and Firstout assigns a unique value like csv:YOUR-REF."
                    value={createForm.our_barcode}
                    onChange={(event) =>
                      setCreateForm((form) => ({ ...form, our_barcode: event.target.value }))
                    }
                  />
                </Column>
                <Column lg={16} md={8} sm={4}>
                  <TextInput
                    id="new-sku-name"
                    labelText="Name *"
                    value={createForm.name}
                    onChange={(event) =>
                      setCreateForm((form) => ({ ...form, name: event.target.value }))
                    }
                    invalid={missing.has("Name")}
                    invalidText="Name is required"
                    required
                  />
                </Column>
                <Column lg={8} md={4} sm={4}>
                  <TextInput
                    id="new-sku-category"
                    labelText="Category"
                    helperText="Optional — e.g. Seating, Tables"
                    value={createForm.category ?? ""}
                    onChange={(event) =>
                      setCreateForm((form) => ({ ...form, category: event.target.value }))
                    }
                  />
                </Column>
                <Column lg={8} md={4} sm={4}>
                  <TextInput
                    id="new-sku-supplier-ref"
                    labelText="Supplier ref"
                    helperText="Supplier's reference — not our barcode"
                    value={createForm.supplier_ref ?? ""}
                    onChange={(event) =>
                      setCreateForm((form) => ({ ...form, supplier_ref: event.target.value }))
                    }
                  />
                </Column>
                <Column lg={8} md={4} sm={4}>
                  <TextInput
                    id="new-sku-design"
                    labelText="Design *"
                    value={createForm.design}
                    onChange={(event) =>
                      setCreateForm((form) => ({ ...form, design: event.target.value }))
                    }
                    invalid={missing.has("Design")}
                    invalidText="Design is required"
                    required
                  />
                </Column>
                <Column lg={8} md={4} sm={4}>
                  <TextInput
                    id="new-sku-fabric"
                    labelText="Fabric *"
                    value={createForm.fabric}
                    onChange={(event) =>
                      setCreateForm((form) => ({ ...form, fabric: event.target.value }))
                    }
                    invalid={missing.has("Fabric")}
                    invalidText="Fabric is required"
                    required
                  />
                </Column>
                <Column lg={8} md={4} sm={4}>
                  <NumberInput
                    id="new-sku-carton-count"
                    label="Cartons"
                    helperText="Sellable unit ships in this many cartons. Default 1. Not a kit BOM."
                    min={1}
                    step={1}
                    allowEmpty
                    value={cartonCount}
                    invalid={missing.has("Cartons")}
                    invalidText="Cartons must be 1 or more"
                    onChange={(_event, { value }) => {
                      setCartonCount(value === "" ? "" : Number(value));
                    }}
                  />
                </Column>
                <Column lg={16} md={8} sm={4}>
                  <div>
                    <p className="cds--label">Photo (optional)</p>
                    <FileUploaderDropContainer
                      accept={SKU_PHOTO_ACCEPT}
                      labelText="Drag and drop an image here or click to upload"
                      multiple={false}
                      onAddFiles={(event, { addedFiles }) => {
                        const picked = pickSkuPhoto(event, addedFiles);
                        if (picked.file) {
                          setPhotoFile(picked.file);
                          setPhotoError(null);
                          return;
                        }
                        setPhotoFile(null);
                        setPhotoError(picked.error ?? "Choose an image file.");
                      }}
                    />
                    {photoError ? (
                      <div id="new-sku-photo-error">
                        <InlineNotification
                          kind="error"
                          title="Photo not added"
                          subtitle={photoError}
                          hideCloseButton
                          lowContrast
                        />
                      </div>
                    ) : null}
                    {photoFile && photoPreviewUrl ? (
                      <img
                        id="new-sku-photo-preview"
                        src={photoPreviewUrl}
                        alt={`Preview of ${photoFile.name}`}
                        width={160}
                        height={160}
                        style={{ objectFit: "cover", marginTop: "1rem" }}
                      />
                    ) : null}
                    {photoFile ? (
                      <FileUploaderItem
                        name={photoFile.name}
                        status="edit"
                        onDelete={() => {
                          setPhotoFile(null);
                          setPhotoError(null);
                        }}
                      />
                    ) : null}
                  </div>
                </Column>
              </Grid>
            </Stack>
          </Tile>

          <Tile>
            <Stack gap={5}>
              <h2 className="cds--type-productive-heading-02">Pricing (ZAR, includes 15% VAT)</h2>
              <p className="cds--type-body-01">
                Enter each price including VAT. Firstout stores the ex-VAT amount at 15%.
              </p>
              <Grid condensed fullWidth>
                <Column lg={8} md={4} sm={4}>
                  <TextInput
                    id="new-sku-stockist-inc-vat"
                    labelText="Stockist inc VAT"
                    helperText="Optional — saved after the SKU is created"
                    value={stockistIncVat}
                    onChange={(event) => setStockistIncVat(event.target.value)}
                  />
                </Column>
                <Column lg={8} md={4} sm={4}>
                  <TextInput
                    id="new-sku-wholesale-inc-vat"
                    labelText="Wholesale inc VAT"
                    helperText="Optional — saved after the SKU is created"
                    value={wholesaleIncVat}
                    onChange={(event) => setWholesaleIncVat(event.target.value)}
                  />
                </Column>
                <Column lg={8} md={4} sm={4}>
                  <TextInput
                    id="new-sku-decorator-inc-vat"
                    labelText="Decorator inc VAT"
                    helperText="Optional — saved after the SKU is created"
                    value={decoratorIncVat}
                    onChange={(event) => setDecoratorIncVat(event.target.value)}
                  />
                </Column>
                <Column lg={8} md={4} sm={4}>
                  <TextInput
                    id="new-sku-retail-inc-vat"
                    labelText="Retail inc VAT"
                    helperText="Optional — saved after the SKU is created"
                    value={retailIncVat}
                    onChange={(event) => setRetailIncVat(event.target.value)}
                  />
                </Column>
              </Grid>
            </Stack>
          </Tile>

          <Tile>
            <Stack gap={5}>
              <div>
                <h2 className="cds--type-productive-heading-02">Initial Opening Stock (Optional)</h2>
                <p className="cds--type-body-01">Optional day-one stock without a PO.</p>
              </div>
              <Checkbox
                id="new-sku-record-stock"
                labelText="Record stock now"
                checked={recordStockNow}
                onChange={(_, { checked }) => setRecordStockNow(checked)}
              />
              {recordStockNow ? (
                <Grid condensed fullWidth>
                  <Column lg={8} md={4} sm={4}>
                    <Select
                      id="new-sku-opening-location"
                      labelText="Location *"
                      value={openingLocationId}
                      onChange={(event) => setOpeningLocationId(event.target.value)}
                      invalid={missing.has("Location")}
                      invalidText="Location is required"
                      required
                      helperText={
                        locations.length === 0 ? "No active locations available" : undefined
                      }
                    >
                      <SelectItem value="" text="Select location" />
                      {locations.map((entry) => (
                        <SelectItem key={entry.id} value={entry.id} text={entry.name} />
                      ))}
                    </Select>
                  </Column>
                  <Column lg={8} md={4} sm={4}>
                    <NumberInput
                      id="new-sku-opening-qty"
                      label="Quantity on Hand *"
                      min={1}
                      step={1}
                      required
                      invalid={missing.has("Quantity on hand")}
                      invalidText="Quantity on hand is required"
                      value={openingQty}
                      onChange={(_event, { value }) => {
                        if (value === "") {
                          setOpeningQty("");
                        } else {
                          setOpeningQty(Number(value));
                        }
                      }}
                    />
                  </Column>
                  <Column lg={8} md={4} sm={4}>
                    <TextInput
                      id="new-sku-opening-unit-cost"
                      labelText="Unit Cost (ZAR) *"
                      helperText="Used for inventory valuation"
                      value={openingUnitCost}
                      onChange={(event) => setOpeningUnitCost(event.target.value)}
                      invalid={missing.has("Unit cost")}
                      invalidText="Enter a unit cost greater than 0"
                      required
                    />
                  </Column>
                  <Column lg={8} md={4} sm={4}>
                    <TextInput
                      id="new-sku-opening-date"
                      labelText="Received Date"
                      type="date"
                      value={openingDate}
                      onChange={(event) => setOpeningDate(event.target.value)}
                    />
                  </Column>
                </Grid>
              ) : null}
            </Stack>
          </Tile>

          {missingMessage ? (
            <div id="new-sku-missing-fields">
              <InlineNotification
                kind="warning"
                title="Save SKU is unavailable"
                subtitle={missingMessage}
                hideCloseButton
                lowContrast
              />
            </div>
          ) : null}

          <Stack gap={4} orientation="horizontal">
            <Button kind="secondary" type="button" disabled={saving} onClick={goBack}>
              Back to catalogue
            </Button>
            <Button
              data-tour="sku-save"
              kind="primary"
              type="submit"
              renderIcon={Save}
              disabled={saving || !formValid}
            >
              {saving ? "Saving…" : "Save SKU"}
            </Button>
          </Stack>
        </Stack>
      </form>
      </Stack>
    </div>
  );
}

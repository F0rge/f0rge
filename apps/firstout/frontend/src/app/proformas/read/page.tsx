"use client";

import {
  Button,
  ComboBox,
  FileUploaderDropContainer,
  FileUploaderItem,
  InlineNotification,
  Modal,
  Select,
  SelectItem,
  Stack,
  TextArea,
  TextInput,
} from "@carbon/react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import {
  canMutateCatalogue,
  confirmProforma,
  createIntakeSku,
  createSupplier,
  extractProforma,
  listSkus,
  listSuppliers,
  suggestIntakeSku,
  type IntakeCharge,
  type ProformaReview,
  type Sku,
  type Supplier,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

type DraftLine = {
  supplier_code: string;
  description: string;
  qty: string;
  unit_price: string;
  sku_id: string;
  skip: boolean;
  match_reason: string;
  confidence: number | null;
  flags: string[];
};

type SkuDraft = {
  our_ref: string;
  our_barcode: string;
  name: string;
  design: string;
  fabric: string;
  category: string;
  supplier_ref: string;
  latest_price: string;
};

const emptySku: SkuDraft = {
  our_ref: "",
  our_barcode: "",
  name: "",
  design: "",
  fabric: "",
  category: "",
  supplier_ref: "",
  latest_price: "",
};

function linesFromReview(review: ProformaReview): DraftLine[] {
  return review.lines.map((line) => ({
    supplier_code: line.supplier_code ?? "",
    description: line.description,
    qty: line.qty_whole != null ? String(line.qty_whole) : line.qty,
    unit_price: line.net_unit_price,
    sku_id: line.match?.sku_id ?? "",
    skip: false,
    match_reason: line.match?.reason ?? "No SKU match yet.",
    confidence: line.match?.confidence ?? null,
    flags: line.flags.map((flag) => flag.message),
  }));
}

export default function ReadProformaPage() {
  const { user } = useAuth();
  const router = useRouter();
  const canMutate = canMutateCatalogue(user);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [reading, setReading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [review, setReview] = useState<ProformaReview | null>(null);
  const [lines, setLines] = useState<DraftLine[]>([]);
  const [charges, setCharges] = useState<IntakeCharge[]>([]);
  const [documentNumber, setDocumentNumber] = useState("");
  const [documentDate, setDocumentDate] = useState("");
  const [currency, setCurrency] = useState("ZAR");
  const [paymentTerms, setPaymentTerms] = useState("");
  const [deposit, setDeposit] = useState("");
  const [createNewSupplier, setCreateNewSupplier] = useState(false);
  const [supplierId, setSupplierId] = useState("");
  const [supplierName, setSupplierName] = useState("");
  const [supplierVat, setSupplierVat] = useState("");
  const [supplierAddress, setSupplierAddress] = useState("");
  const [hint, setHint] = useState("");
  const [catalogue, setCatalogue] = useState<Sku[]>([]);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [skuOpen, setSkuOpen] = useState(false);
  const [skuLine, setSkuLine] = useState<number | null>(null);
  const [skuDraft, setSkuDraft] = useState<SkuDraft>(emptySku);
  const [skuSaving, setSkuSaving] = useState(false);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  useEffect(() => {
    if (!canMutate) {
      return;
    }
    listSkus()
      .then(setCatalogue)
      .catch(() => setCatalogue([]));
    listSuppliers()
      .then(setSuppliers)
      .catch(() => setSuppliers([]));
  }, [canMutate]);

  const skuItems = useMemo(
    () =>
      catalogue.map((sku) => ({
        id: sku.id,
        label: `${sku.our_ref} — ${sku.name}`,
      })),
    [catalogue],
  );

  function onFile(next: File) {
    setFile(next);
    setReview(null);
    setError(null);
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(URL.createObjectURL(next));
  }

  async function readDocument() {
    if (!file) {
      return;
    }
    setReading(true);
    setError(null);
    try {
      const result = await extractProforma(file);
      setReview(result);
      setLines(linesFromReview(result));
      setCharges(result.charges);
      setDocumentNumber(result.document_number);
      setDocumentDate(result.document_date ?? "");
      setCurrency(result.currency || "ZAR");
      setPaymentTerms(result.payment_terms ?? "");
      setDeposit(result.deposit ?? "");
      setSupplierName(result.supplier.name);
      setSupplierVat(result.supplier.vat_number ?? "");
      setSupplierAddress(result.supplier.address ?? "");
      setSupplierId(result.supplier.supplier_id ?? "");
      setCreateNewSupplier(result.supplier.supplier_id == null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not read that document.");
    } finally {
      setReading(false);
    }
  }

  function patchLine(index: number, patch: Partial<DraftLine>) {
    setLines((current) => current.map((line, i) => (i === index ? { ...line, ...patch } : line)));
  }

  async function saveNewSupplier() {
    if (!supplierName.trim()) {
      setError("Type the supplier name before saving them.");
      return;
    }
    setError(null);
    try {
      const created = await createSupplier({
        name: supplierName.trim(),
        default_currency: currency,
        vat_number: supplierVat.trim() || null,
        address: supplierAddress.trim() || null,
      });
      setSuppliers((current) => [...current, created]);
      setSupplierId(created.id);
      setCreateNewSupplier(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create that supplier.");
    }
  }

  async function openSku(index: number) {
    const line = lines[index];
    setSkuLine(index);
    setSkuOpen(true);
    setSkuSaving(true);
    try {
      const suggestion = await suggestIntakeSku({
        description: line.description,
        supplier_code: line.supplier_code || null,
        unit_price: line.unit_price || null,
        currency,
        hint: hint.trim() || null,
        supplier_id: supplierId || null,
      });
      setSkuDraft({
        our_ref: suggestion.our_ref,
        our_barcode: suggestion.our_barcode,
        name: suggestion.name,
        design: suggestion.design,
        fabric: suggestion.fabric,
        category: suggestion.category ?? "",
        supplier_ref: suggestion.supplier_ref ?? line.supplier_code,
        latest_price: suggestion.cost_price ?? line.unit_price,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not suggest a SKU.");
      setSkuDraft({
        ...emptySku,
        name: line.description,
        design: line.description,
        fabric: "Unspecified",
        supplier_ref: line.supplier_code,
        latest_price: line.unit_price,
      });
    } finally {
      setSkuSaving(false);
    }
  }

  async function saveSku() {
    if (skuLine == null) {
      return;
    }
    const resolvedSupplier = supplierId;
    if (!resolvedSupplier) {
      setError("Save the supplier first, then create the SKU.");
      return;
    }
    setSkuSaving(true);
    setError(null);
    try {
      const created = await createIntakeSku({
        our_ref: skuDraft.our_ref.trim(),
        our_barcode: skuDraft.our_barcode.trim(),
        name: skuDraft.name.trim(),
        design: skuDraft.design.trim(),
        fabric: skuDraft.fabric.trim(),
        category: skuDraft.category.trim() || null,
        supplier_ref: skuDraft.supplier_ref.trim() || null,
        supplier_id: resolvedSupplier,
        supplier_sku: skuDraft.supplier_ref.trim() || null,
        latest_price: skuDraft.latest_price.trim() || null,
      });
      patchLine(skuLine, {
        sku_id: created.sku.id,
        match_reason: `New SKU ${created.sku.our_ref}.`,
        confidence: 1,
      });
      setCatalogue((current) => [...current, created.sku]);
      setSkuOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create that SKU.");
    } finally {
      setSkuSaving(false);
    }
  }

  async function confirm() {
    if (!file || !review) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const result = await confirmProforma(file, {
        supplier_id: createNewSupplier ? null : supplierId,
        create_supplier: createNewSupplier
          ? {
              name: supplierName.trim(),
              vat_number: supplierVat.trim() || null,
              address: supplierAddress.trim() || null,
              default_currency: currency,
            }
          : null,
        document_number: documentNumber.trim(),
        document_date: documentDate,
        currency: currency.trim(),
        payment_terms: paymentTerms.trim() || null,
        deposit: deposit.trim() || null,
        vat_total: review.vat_total,
        total: review.total,
        charges: charges
          .filter((charge) => charge.description.trim())
          .map((charge) => ({ description: charge.description.trim(), amount: charge.amount })),
        lines: lines.map((line) => ({
          supplier_code: line.supplier_code || null,
          description: line.description,
          qty: Number(line.qty),
          unit_price: line.unit_price,
          sku_id: line.skip ? null : line.sku_id || null,
          skip: line.skip,
        })),
      });
      router.push(`/purchase-orders/${result.purchase_order.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the purchase order.");
      setSaving(false);
    }
  }

  const keptWithoutSku = lines.some((line) => !line.skip && !line.sku_id);
  const canConfirm =
    review != null &&
    documentNumber.trim() &&
    documentDate &&
    (createNewSupplier ? supplierName.trim() : supplierId) &&
    !keptWithoutSku &&
    lines.some((line) => !line.skip);

  if (!canMutate) {
    return (
      <InlineNotification
        kind="warning"
        title="Buyers and owners"
        subtitle="Reading a proforma into a purchase order needs the same access as raising a purchase order."
        hideCloseButton
        lowContrast
      />
    );
  }

  return (
    <Stack gap={6}>
      <div className="firstout-page-header">
        <div>
          <h1 className="cds--type-productive-heading-04">Read a proforma</h1>
          <p className="cds--type-body-01">
            Nothing is saved until you confirm. The purchase order is then open, the same as one typed in by hand.
          </p>
        </div>
      </div>

      {error ? (
        <InlineNotification
          kind="error"
          title="Check this"
          subtitle={error}
          onCloseButtonClick={() => setError(null)}
          lowContrast
        />
      ) : null}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: review ? "minmax(280px, 1fr) minmax(320px, 1.2fr)" : "1fr",
          gap: "1.5rem",
          alignItems: "start",
        }}
      >
        <Stack gap={4}>
          <FileUploaderDropContainer
            accept={[".pdf", ".png", ".jpg", ".jpeg"]}
            labelText="Drop a PDF or photo, or click to upload"
            onAddFiles={(_event, { addedFiles }) => {
              const added = addedFiles[0];
              if (added) {
                onFile(added);
              }
            }}
          />
          {file ? (
            <FileUploaderItem
              name={file.name}
              status="edit"
              onDelete={() => {
                setFile(null);
                setReview(null);
                if (previewUrl) {
                  URL.revokeObjectURL(previewUrl);
                }
                setPreviewUrl(null);
              }}
            />
          ) : null}
          <Button disabled={!file || reading} onClick={() => void readDocument()}>
            {reading ? "Reading…" : "Read document"}
          </Button>
          {previewUrl && file?.type.startsWith("image/") ? (
            <img alt="Uploaded proforma" src={previewUrl} style={{ maxWidth: "100%" }} />
          ) : null}
          {previewUrl && file && !file.type.startsWith("image/") ? (
            <iframe
              title="Proforma preview"
              src={previewUrl}
              style={{ width: "100%", height: "70vh", border: "1px solid #e0e0e0" }}
            />
          ) : null}
        </Stack>

        {review ? (
          <Stack gap={5}>
            <p className="cds--type-helper-text-01">
              Read with {review.usage.model}. {review.usage.total_tokens} tokens. Nothing is filed yet.
            </p>
            {review.flags.map((flag) => (
              <InlineNotification
                key={flag.code}
                kind={flag.code === "duplicate_proforma" ? "error" : "warning"}
                title="Check this"
                subtitle={flag.message}
                hideCloseButton
                lowContrast
              />
            ))}

            <Select
              id="supplier-mode"
              labelText="Supplier"
              value={createNewSupplier ? "create" : "existing"}
              onChange={(event) => setCreateNewSupplier(event.target.value === "create")}
            >
              <SelectItem value="existing" text="Use an existing supplier" />
              <SelectItem value="create" text="Create a new supplier" />
            </Select>
            <p className="cds--type-helper-text-01">{review.supplier.reason}</p>
            {createNewSupplier ? (
              <Stack gap={3}>
                <TextInput
                  id="new-supplier-name"
                  labelText="Supplier name"
                  value={supplierName}
                  onChange={(event) => setSupplierName(event.target.value)}
                />
                <TextInput
                  id="new-supplier-vat"
                  labelText="VAT number"
                  value={supplierVat}
                  onChange={(event) => setSupplierVat(event.target.value)}
                />
                <TextInput
                  id="new-supplier-address"
                  labelText="Address"
                  value={supplierAddress}
                  onChange={(event) => setSupplierAddress(event.target.value)}
                />
              </Stack>
            ) : (
              <Select
                id="existing-supplier"
                labelText="Matched supplier"
                value={supplierId}
                onChange={(event) => setSupplierId(event.target.value)}
              >
                <SelectItem value="" text="Choose a supplier" />
                {suppliers.map((row) => (
                  <SelectItem key={row.id} value={row.id} text={row.name} />
                ))}
              </Select>
            )}
            {createNewSupplier ? (
              <Button kind="tertiary" size="sm" onClick={() => void saveNewSupplier()}>
                Save supplier so you can add SKUs
              </Button>
            ) : null}

            <TextInput
              id="proforma-number"
              labelText="Proforma number"
              value={documentNumber}
              onChange={(event) => setDocumentNumber(event.target.value)}
            />
            <TextInput
              id="proforma-date"
              labelText="Date"
              type="date"
              value={documentDate}
              onChange={(event) => setDocumentDate(event.target.value)}
            />
            <TextInput
              id="proforma-currency"
              labelText="Currency"
              value={currency}
              onChange={(event) => setCurrency(event.target.value.toUpperCase())}
            />
            <TextInput
              id="payment-terms"
              labelText="Payment terms"
              value={paymentTerms}
              onChange={(event) => setPaymentTerms(event.target.value)}
            />
            <TextInput
              id="deposit"
              labelText="Deposit"
              value={deposit}
              onChange={(event) => setDeposit(event.target.value)}
            />

            <TextArea
              id="sku-hint"
              labelText="Plain-language hint for new SKUs"
              helperText="Optional. For example: these are all cushions, use category Soft Furnishings. You still confirm each SKU."
              value={hint}
              onChange={(event) => setHint(event.target.value)}
            />

            {lines.map((line, index) => (
              <div key={`${line.supplier_code}-${index}`} style={{ borderTop: "1px solid #e0e0e0", paddingTop: "1rem" }}>
                <Stack gap={3}>
                  <strong>
                    Line {index + 1}
                    {line.confidence != null ? ` · ${Math.round(line.confidence * 100)}%` : ""}
                  </strong>
                  <p className="cds--type-helper-text-01">{line.match_reason}</p>
                  {line.flags.map((message) => (
                    <InlineNotification
                      key={message}
                      kind="warning"
                      title="Line"
                      subtitle={message}
                      hideCloseButton
                      lowContrast
                    />
                  ))}
                  <TextInput
                    id={`desc-${index}`}
                    labelText="Description"
                    value={line.description}
                    onChange={(event) => patchLine(index, { description: event.target.value })}
                  />
                  <TextInput
                    id={`code-${index}`}
                    labelText="Supplier code"
                    value={line.supplier_code}
                    onChange={(event) => patchLine(index, { supplier_code: event.target.value })}
                  />
                  <TextInput
                    id={`qty-${index}`}
                    labelText="Quantity"
                    value={line.qty}
                    onChange={(event) => patchLine(index, { qty: event.target.value })}
                  />
                  <TextInput
                    id={`price-${index}`}
                    labelText="Unit price after discount"
                    value={line.unit_price}
                    onChange={(event) => patchLine(index, { unit_price: event.target.value })}
                  />
                  <ComboBox
                    id={`sku-${index}`}
                    titleText="Link to an existing SKU"
                    items={skuItems}
                    itemToString={(item) => item?.label ?? ""}
                    selectedItem={skuItems.find((item) => item.id === line.sku_id) ?? null}
                    onChange={({ selectedItem }) => {
                      if (selectedItem) {
                        patchLine(index, {
                          sku_id: selectedItem.id,
                          skip: false,
                          match_reason: "Linked by you.",
                          confidence: 1,
                        });
                      }
                    }}
                  />
                  <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                    <Button kind="tertiary" size="sm" onClick={() => void openSku(index)} disabled={!supplierId}>
                      Create new SKU
                    </Button>
                    <Button
                      kind={line.skip ? "danger" : "ghost"}
                      size="sm"
                      onClick={() => patchLine(index, { skip: !line.skip })}
                    >
                      {line.skip ? "Skipped — put it back" : "Skip this line"}
                    </Button>
                  </div>
                </Stack>
              </div>
            ))}

            {charges.map((charge, index) => (
              <TextInput
                key={`${charge.description}-${index}`}
                id={`charge-${index}`}
                labelText={charge.description || "Other charge"}
                helperText="Shown for checking. Shipping is not a purchase-order line; it is added when the shipment is landed."
                value={charge.amount}
                onChange={(event) =>
                  setCharges((current) =>
                    current.map((row, i) => (i === index ? { ...row, amount: event.target.value } : row)),
                  )
                }
              />
            ))}
            <p className="cds--type-body-01">
              Document total {review.total ?? "not read"}. Lines, VAT and charges come to {review.computed_total}.
            </p>
            <Button disabled={!canConfirm || saving} onClick={() => void confirm()}>
              {saving ? "Saving…" : "Confirm and create purchase order"}
            </Button>
            {keptWithoutSku ? (
              <p className="cds--type-helper-text-01">
                Each kept line needs a SKU. Create one, link one, or skip the line.
              </p>
            ) : null}
          </Stack>
        ) : null}
      </div>

      <Modal
        open={skuOpen}
        modalHeading="Create a SKU"
        primaryButtonText={skuSaving ? "Saving…" : "Create SKU"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={skuSaving || !supplierId}
        onRequestSubmit={() => void saveSku()}
        onRequestClose={() => setSkuOpen(false)}
      >
        <Stack gap={4}>
          <TextInput id="sku-ref" labelText="Our ref" value={skuDraft.our_ref} onChange={(event) => setSkuDraft({ ...skuDraft, our_ref: event.target.value })} />
          <TextInput id="sku-barcode" labelText="Our barcode" value={skuDraft.our_barcode} onChange={(event) => setSkuDraft({ ...skuDraft, our_barcode: event.target.value })} />
          <TextInput id="sku-name" labelText="Name" value={skuDraft.name} onChange={(event) => setSkuDraft({ ...skuDraft, name: event.target.value })} />
          <TextInput id="sku-design" labelText="Design" value={skuDraft.design} onChange={(event) => setSkuDraft({ ...skuDraft, design: event.target.value })} />
          <TextInput id="sku-fabric" labelText="Fabric" value={skuDraft.fabric} onChange={(event) => setSkuDraft({ ...skuDraft, fabric: event.target.value })} />
          <TextInput id="sku-category" labelText="Category" value={skuDraft.category} onChange={(event) => setSkuDraft({ ...skuDraft, category: event.target.value })} />
          <TextInput id="sku-supplier-code" labelText="Supplier code" value={skuDraft.supplier_ref} onChange={(event) => setSkuDraft({ ...skuDraft, supplier_ref: event.target.value })} />
          <TextInput id="sku-cost" labelText="Cost price on this document" value={skuDraft.latest_price} onChange={(event) => setSkuDraft({ ...skuDraft, latest_price: event.target.value })} />
        </Stack>
      </Modal>
    </Stack>
  );
}

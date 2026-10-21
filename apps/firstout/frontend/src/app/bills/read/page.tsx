"use client";

import {
  Button,
  Checkbox,
  FileUploaderDropContainer,
  FileUploaderItem,
  InlineNotification,
  Select,
  SelectItem,
  Stack,
  TextInput,
} from "@carbon/react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  canMutateBooks,
  createSupplier,
  extractSupplierInvoice,
  listSkus,
  listSuppliers,
  processSupplierInvoice,
  type IntakeCharge,
  type InvoiceReview,
  type Sku,
  type Supplier,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";

type DraftLine = {
  supplier_code: string;
  description: string;
  qty: string;
  unit_price: string;
  discount_percent: string;
  sku_id: string;
  skip: boolean;
  match_reason: string;
  confidence: number | null;
  flags: string[];
};

function linesFromReview(review: InvoiceReview): DraftLine[] {
  return review.lines.map((line) => ({
    supplier_code: line.supplier_code ?? "",
    description: line.description,
    qty: line.qty_whole != null ? String(line.qty_whole) : line.qty,
    unit_price: line.net_unit_price,
    discount_percent: line.discount_percent ?? "",
    sku_id: line.match?.sku_id ?? "",
    skip: false,
    match_reason: line.match?.reason ?? "No SKU match yet.",
    confidence: line.match?.confidence ?? null,
    flags: line.flags.map((flag) => flag.message),
  }));
}

export default function ReadSupplierInvoicePage() {
  const { user } = useAuth();
  const router = useRouter();
  const canMutate = canMutateBooks(user);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [reading, setReading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [review, setReview] = useState<InvoiceReview | null>(null);
  const [lines, setLines] = useState<DraftLine[]>([]);
  const [charges, setCharges] = useState<IntakeCharge[]>([]);
  const [documentNumber, setDocumentNumber] = useState("");
  const [documentDate, setDocumentDate] = useState("");
  const [currency, setCurrency] = useState("ZAR");
  const [fxToZar, setFxToZar] = useState("");
  const [vatTotal, setVatTotal] = useState("");
  const [total, setTotal] = useState("");
  const [supplierId, setSupplierId] = useState("");
  const [supplierName, setSupplierName] = useState("");
  const [supplierVat, setSupplierVat] = useState("");
  const [purchaseOrderId, setPurchaseOrderId] = useState("");
  const [acceptDifferences, setAcceptDifferences] = useState(false);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [catalogue, setCatalogue] = useState<Sku[]>([]);

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
    void Promise.all([listSuppliers(), listSkus()])
      .then(([supplierRows, skuRows]) => {
        setSuppliers(supplierRows);
        setCatalogue(skuRows);
      })
      .catch(() => {
        setError("Could not load suppliers and SKUs.");
      });
  }, [canMutate]);

  function onFile(next: File) {
    setFile(next);
    setReview(null);
    setNotice(null);
    setAcceptDifferences(false);
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(URL.createObjectURL(next));
  }

  function applyReview(body: InvoiceReview) {
    setReview(body);
    setLines(linesFromReview(body));
    setCharges(body.charges);
    setDocumentNumber(body.document_number);
    setDocumentDate(body.document_date ?? "");
    setCurrency(body.currency);
    setVatTotal(body.vat_total ?? "");
    setTotal(body.total ?? "");
    setSupplierId(body.supplier.supplier_id ?? "");
    setSupplierName(body.supplier.name);
    setSupplierVat(body.supplier.vat_number ?? "");
    setPurchaseOrderId(body.purchase_order?.purchase_order_id ?? "");
    setAcceptDifferences(false);
    if (body.processed) {
      setNotice(
        body.processed.auto
          ? `Posted ${body.processed.bill_number} against ${body.processed.po_number}. It is on the books like a bill typed in by hand. Reverse it with a journal if this was wrong.`
          : `Posted ${body.processed.bill_number}.`,
      );
    }
  }

  async function readDocument() {
    if (!file) {
      return;
    }
    setReading(true);
    setError(null);
    setNotice(null);
    try {
      applyReview(await extractSupplierInvoice(file));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not read this invoice.");
    } finally {
      setReading(false);
    }
  }

  function patchLine(index: number, patch: Partial<DraftLine>) {
    setLines((current) =>
      current.map((line, lineIndex) => (lineIndex === index ? { ...line, ...patch } : line)),
    );
  }

  async function saveNewSupplier() {
    setError(null);
    try {
      const created = await createSupplier({
        name: supplierName.trim(),
        default_currency: currency.trim() || "ZAR",
        vat_number: supplierVat.trim() || null,
      });
      setSuppliers((current) => [...current, created]);
      setSupplierId(created.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the supplier.");
    }
  }

  async function processInvoice() {
    if (!file || !review) {
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const result = await processSupplierInvoice(file, {
        supplier_id: supplierId,
        purchase_order_id: purchaseOrderId,
        document_number: documentNumber.trim(),
        document_date: documentDate,
        currency: currency.trim(),
        fx_to_zar: currency.trim().toUpperCase() === "ZAR" ? null : fxToZar.trim(),
        accept_differences: acceptDifferences || review.exact,
        vat_total: vatTotal.trim() || null,
        total: total.trim() || null,
        charges: charges
          .filter((charge) => charge.description.trim())
          .map((charge) => ({ description: charge.description.trim(), amount: charge.amount })),
        lines: lines.map((line) => ({
          supplier_code: line.supplier_code || null,
          description: line.description,
          qty: Number(line.qty),
          unit_price: line.unit_price,
          discount_percent: line.discount_percent || null,
          sku_id: line.skip ? null : line.sku_id || null,
          skip: line.skip,
        })),
      });
      router.push(`/bills/${result.bill_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not post this invoice.");
      setSaving(false);
    }
  }

  function rejectInvoice() {
    setReview(null);
    setLines([]);
    setNotice("Invoice was not posted.");
    setAcceptDifferences(false);
  }

  const keptWithoutSku = lines.some((line) => !line.skip && !line.sku_id);
  const needsFx = currency.trim().toUpperCase() !== "ZAR";
  const canProcess =
    review != null &&
    review.processed == null &&
    documentNumber.trim() &&
    documentDate &&
    supplierId &&
    purchaseOrderId &&
    !keptWithoutSku &&
    lines.some((line) => !line.skip) &&
    (review.exact || acceptDifferences) &&
    (!needsFx || fxToZar.trim());

  if (!canMutate) {
    return (
      <InlineNotification
        kind="warning"
        title="Books access"
        subtitle="Posting a supplier invoice needs the same access as creating a bill."
        hideCloseButton
        lowContrast
      />
    );
  }

  return (
    <Stack gap={6}>
      <div className="firstout-page-header">
        <div>
          <h1 className="cds--type-productive-heading-04">Read a supplier invoice</h1>
          <p className="cds--type-body-01">
            The invoice is checked against the purchase order. An exact match can be posted in one
            click. Anything different stays here until you accept the invoice figures or reject them.
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
      {notice ? (
        <InlineNotification
          kind="success"
          title="Invoice"
          subtitle={notice}
          onCloseButtonClick={() => setNotice(null)}
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
            <img alt="Uploaded supplier invoice" src={previewUrl} style={{ maxWidth: "100%" }} />
          ) : null}
          {previewUrl && file && !file.type.startsWith("image/") ? (
            <iframe
              title="Invoice preview"
              src={previewUrl}
              style={{ width: "100%", height: "70vh", border: "1px solid #e0e0e0" }}
            />
          ) : null}
        </Stack>

        {review ? (
          <Stack gap={5}>
            <p className="cds--type-helper-text-01">
              Read with {review.usage.model}. {review.usage.total_tokens} tokens.
              {review.auto_process_enabled
                ? " Auto-process is on, so an exact rand match is posted immediately."
                : " Auto-process is off, so an exact match still waits for Process."}
            </p>
            {review.flags.map((flag) => (
              <InlineNotification
                key={flag.code}
                kind={flag.code === "duplicate_invoice" ? "error" : "warning"}
                title="Check this"
                subtitle={flag.message}
                hideCloseButton
                lowContrast
              />
            ))}
            {review.differences.map((difference) => (
              <InlineNotification
                key={difference}
                kind="warning"
                title="Does not match the order"
                subtitle={difference}
                hideCloseButton
                lowContrast
              />
            ))}
            {review.exact && review.processed == null ? (
              <InlineNotification
                kind="success"
                title="Exact match"
                subtitle="Quantities, prices, VAT and the total agree with the purchase order, within one cent."
                hideCloseButton
                lowContrast
              />
            ) : null}
            <p className="cds--type-helper-text-01">{review.supplier.reason}</p>
            <Select
              id="invoice-supplier"
              labelText="Supplier"
              value={supplierId}
              onChange={(event) => setSupplierId(event.target.value)}
            >
              <SelectItem value="" text="Choose a supplier" />
              {suppliers.map((row) => (
                <SelectItem key={row.id} value={row.id} text={row.name} />
              ))}
            </Select>
            {!supplierId ? (
              <Stack gap={3}>
                <TextInput
                  id="new-invoice-supplier"
                  labelText="New supplier name"
                  value={supplierName}
                  onChange={(event) => setSupplierName(event.target.value)}
                />
                <TextInput
                  id="new-invoice-vat"
                  labelText="VAT number"
                  value={supplierVat}
                  onChange={(event) => setSupplierVat(event.target.value)}
                />
                <Button
                  kind="tertiary"
                  size="sm"
                  disabled={!supplierName.trim()}
                  onClick={() => void saveNewSupplier()}
                >
                  Save supplier
                </Button>
              </Stack>
            ) : null}
            <Select
              id="invoice-po"
              labelText="Purchase order"
              value={purchaseOrderId}
              onChange={(event) => setPurchaseOrderId(event.target.value)}
            >
              <SelectItem value="" text="Choose the purchase order" />
              {review.purchase_order_candidates.map((row) => (
                <SelectItem
                  key={row.purchase_order_id}
                  value={row.purchase_order_id}
                  text={`${row.po_number} · ${row.status.replaceAll("_", " ")}`}
                />
              ))}
            </Select>
            <TextInput
              id="invoice-number"
              labelText="Invoice number"
              value={documentNumber}
              onChange={(event) => setDocumentNumber(event.target.value)}
            />
            <TextInput
              id="invoice-date"
              labelText="Date"
              type="date"
              value={documentDate}
              onChange={(event) => setDocumentDate(event.target.value)}
            />
            <TextInput
              id="invoice-currency"
              labelText="Currency"
              value={currency}
              onChange={(event) => setCurrency(event.target.value.toUpperCase())}
            />
            {needsFx ? (
              <TextInput
                id="invoice-fx"
                labelText="Rand value of 1 unit of this currency"
                value={fxToZar}
                onChange={(event) => setFxToZar(event.target.value)}
              />
            ) : null}
            <TextInput
              id="invoice-vat"
              labelText="VAT total"
              value={vatTotal}
              onChange={(event) => setVatTotal(event.target.value)}
            />
            <TextInput
              id="invoice-total"
              labelText="Invoice total"
              value={total}
              onChange={(event) => setTotal(event.target.value)}
            />
            {charges.map((charge, index) => (
              <TextInput
                key={`${charge.description}-${index}`}
                id={`charge-${index}`}
                labelText={charge.description || "Charge"}
                value={charge.amount}
                onChange={(event) =>
                  setCharges((current) =>
                    current.map((row, rowIndex) =>
                      rowIndex === index ? { ...row, amount: event.target.value } : row,
                    ),
                  )
                }
              />
            ))}
            {lines.map((line, index) => (
              <div
                key={`${line.supplier_code}-${index}`}
                style={{ borderTop: "1px solid #e0e0e0", paddingTop: "1rem" }}
              >
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
                    id={`inv-desc-${index}`}
                    labelText="Description"
                    value={line.description}
                    onChange={(event) => patchLine(index, { description: event.target.value })}
                  />
                  <TextInput
                    id={`inv-qty-${index}`}
                    labelText="Quantity"
                    value={line.qty}
                    onChange={(event) => patchLine(index, { qty: event.target.value })}
                  />
                  <TextInput
                    id={`inv-price-${index}`}
                    labelText="Unit price after discount"
                    value={line.unit_price}
                    onChange={(event) => patchLine(index, { unit_price: event.target.value })}
                  />
                  <Select
                    id={`inv-sku-${index}`}
                    labelText="SKU"
                    value={line.sku_id}
                    onChange={(event) => patchLine(index, { sku_id: event.target.value })}
                  >
                    <SelectItem value="" text="No SKU" />
                    {catalogue.map((sku) => (
                      <SelectItem key={sku.id} value={sku.id} text={`${sku.our_ref} · ${sku.name}`} />
                    ))}
                  </Select>
                  <Checkbox
                    id={`inv-skip-${index}`}
                    labelText="Skip this line"
                    checked={line.skip}
                    onChange={(_, { checked }) => patchLine(index, { skip: checked })}
                  />
                </Stack>
              </div>
            ))}
            {!review.exact && review.processed == null ? (
              <Checkbox
                id="accept-invoice-differences"
                labelText="Use the invoice figures"
                checked={acceptDifferences}
                onChange={(_, { checked }) => setAcceptDifferences(checked)}
              />
            ) : null}
            {review.processed == null ? (
              <div style={{ display: "flex", gap: "0.75rem" }}>
                <Button disabled={!canProcess || saving} onClick={() => void processInvoice()}>
                  {saving ? "Posting…" : review.exact ? "Process" : "Process using the invoice figures"}
                </Button>
                <Button kind="danger--tertiary" onClick={rejectInvoice}>
                  Reject
                </Button>
              </div>
            ) : (
              <Button kind="secondary" href={`/bills/${review.processed.bill_id}`}>
                Open {review.processed.bill_number}
              </Button>
            )}
          </Stack>
        ) : null}
      </div>
    </Stack>
  );
}

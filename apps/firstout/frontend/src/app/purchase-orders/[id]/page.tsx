"use client";

import {
  Button,
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
  TextArea,
  TextInput,
} from "@carbon/react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  ApiError,
  PO_STATUS_LABELS,
  approvePurchaseOrder,
  can,
  canMutateCatalogue,
  canRaisePo,
  canReceive,
  createPurchaseOrderLineSku,
  downloadPackingSheet,
  downloadPurchaseOrder,
  getPurchaseOrder,
  landPurchaseOrder,
  listSkus,
  listSuppliers,
  markOnWater,
  rejectPurchaseOrder,
  updatePurchaseOrderLines,
  type PurchaseOrder,
  type Sku,
  type Supplier,
} from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  displayFabric,
  lookupManufacturerCode,
  supplierCodeWhenBlank,
} from "@/lib/po-supplier-code";

type BillForm = {
  invoice_number: string;
  amount: string;
  currency: string;
  file: File | null;
};

const emptyBill = (currency = "USD"): BillForm => ({
  invoice_number: "",
  amount: "",
  currency,
  file: null,
});

type DraftLine = {
  key: string;
  id?: string;
  sku_id: string;
  supplier_code: string;
  description: string;
  notes: string;
  qty: number | "";
  factory_unit_amount: string;
};

type SkuDraft = {
  our_ref: string;
  our_barcode: string;
  name: string;
  design: string;
  fabric: string;
};

function draftsFromOrder(order: PurchaseOrder): DraftLine[] {
  return order.lines.map((line) => ({
    key: line.id,
    id: line.id,
    sku_id: line.sku_id ?? "",
    supplier_code: line.supplier_code ?? "",
    description: line.description ?? "",
    notes: line.notes ?? "",
    qty: line.qty,
    factory_unit_amount: line.factory_unit_amount,
  }));
}

function placeholderRef(supplierCode: string, description: string): string {
  const fromCode = supplierCode.trim().replace(/\s+/g, "-").slice(0, 64);
  if (fromCode) {
    return fromCode;
  }
  const slug = description
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64);
  return slug || "NEW-SKU";
}

function skuDefaults(line: DraftLine): SkuDraft {
  const ref = placeholderRef(line.supplier_code, line.description);
  const tagged = `csv:${ref}`.slice(0, 64);
  return {
    our_ref: ref,
    our_barcode: tagged,
    name: line.description.trim() || ref,
    design: tagged,
    fabric: "-",
  };
}

const blankSkuDraft = (): SkuDraft => ({
  our_ref: "",
  our_barcode: "",
  name: "",
  design: "",
  fabric: "-",
});

export default function PurchaseOrderDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useAuth();
  const canRaise = canRaisePo(user);
  const canRecv = canReceive(user);
  const canApprovePo = can(user, "users.manage");
  const canEditLines = canMutateCatalogue(user) || canApprovePo;
  const [order, setOrder] = useState<PurchaseOrder | null>(null);
  const [skus, setSkus] = useState<Sku[]>([]);
  const [draftLines, setDraftLines] = useState<DraftLine[]>([]);
  const [supplierRef, setSupplierRef] = useState("");
  const [headerNotes, setHeaderNotes] = useState("");
  const [skuOpen, setSkuOpen] = useState(false);
  const [skuLineKey, setSkuLineKey] = useState<string | null>(null);
  const [skuDraft, setSkuDraft] = useState<SkuDraft>(blankSkuDraft());
  const [supplier, setSupplier] = useState<Supplier | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [landOpen, setLandOpen] = useState(false);
  const [fxToZar, setFxToZar] = useState("");
  const [factoryBill, setFactoryBill] = useState<BillForm>(emptyBill("USD"));
  const [freightBill, setFreightBill] = useState<BillForm>(emptyBill("USD"));
  const [clearanceBill, setClearanceBill] = useState<BillForm>(emptyBill("ZAR"));

  const loadOrder = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getPurchaseOrder(params.id);
      setOrder(data);
      setDraftLines(draftsFromOrder(data));
      setSupplierRef(data.supplier_ref ?? "");
      setHeaderNotes(data.notes ?? "");
      const suppliers = await listSuppliers();
      const matched = suppliers.find((entry) => entry.id === data.supplier_id) ?? null;
      setSupplier(matched);
      if (matched) {
        setFactoryBill((current) => ({ ...current, currency: matched.default_currency }));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load purchase order.");
    } finally {
      setLoading(false);
    }
  }, [params.id]);

  useEffect(() => {
    if (user && params.id) {
      void loadOrder();
    }
  }, [user, params.id, loadOrder]);

  useEffect(() => {
    if (!canEditLines || order?.status !== "pending_approval") {
      return;
    }
    void listSkus()
      .then(setSkus)
      .catch(() => setSkus([]));
  }, [canEditLines, order?.status, order?.id]);

  const editingPending = Boolean(
    order && order.status === "pending_approval" && canEditLines,
  );

  useEffect(() => {
    if (!editingPending || !order || skus.length === 0) {
      return;
    }
    let cancelled = false;
    const supplierId = order.supplier_id;
    void (async () => {
      const filled = await Promise.all(
        order.lines.map(async (line) => {
          if ((line.supplier_code ?? "").trim() || !line.sku_id) {
            return line.supplier_code ?? "";
          }
          const sku = skus.find((item) => item.id === line.sku_id);
          if (!sku) {
            return "";
          }
          return lookupManufacturerCode(supplierId, sku);
        }),
      );
      if (cancelled) {
        return;
      }
      setDraftLines((current) =>
        current.map((line) => {
          const index = order.lines.findIndex((row) => row.id === line.id);
          if (index < 0 || line.supplier_code.trim()) {
            return line;
          }
          return {
            ...line,
            supplier_code: supplierCodeWhenBlank(line.supplier_code, filled[index] ?? ""),
          };
        }),
      );
    })();
    return () => {
      cancelled = true;
    };
  }, [editingPending, order, skus]);

  async function handleDownload() {
    if (!order) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await downloadPackingSheet(order.id, order.po_number);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download packing sheet.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleDownloadPurchaseOrder() {
    if (!order) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      await downloadPurchaseOrder(order.id, order.po_number);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to download the purchase order.");
    } finally {
      setActionLoading(false);
    }
  }

  function onDraftSkuPicked(key: string, skuId: string) {
    updateDraft(key, { sku_id: skuId });
    const sku = skus.find((item) => item.id === skuId);
    if (!sku || !order) {
      return;
    }
    const supplierId = order.supplier_id;
    void lookupManufacturerCode(supplierId, sku).then((code) => {
      setDraftLines((current) =>
        current.map((line) => {
          if (line.key !== key || line.sku_id !== skuId) {
            return line;
          }
          return { ...line, supplier_code: supplierCodeWhenBlank(line.supplier_code, code) };
        }),
      );
    });
  }

  async function handleApprove() {
    if (!order) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const updated = await approvePurchaseOrder(order.id);
      setOrder(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to approve purchase order.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleReject() {
    if (!order) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const updated = await rejectPurchaseOrder(order.id);
      setOrder(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reject purchase order.");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleMarkOnWater() {
    if (!order) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const updated = await markOnWater(order.id);
      setOrder(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to mark on water.");
    } finally {
      setActionLoading(false);
    }
  }

  function openLandModal() {
    setFxToZar("");
    setFactoryBill(emptyBill(supplier?.default_currency ?? "USD"));
    setFreightBill(emptyBill("USD"));
    setClearanceBill(emptyBill("ZAR"));
    setLandOpen(true);
  }

  function billValid(bill: BillForm): boolean {
    return Boolean(bill.invoice_number.trim() && bill.amount.trim() && bill.currency.trim() && bill.file);
  }

  const landValid = fxToZar.trim() && billValid(factoryBill) && billValid(freightBill) && billValid(clearanceBill);

  async function handleLand() {
    if (!order || !landValid) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("fx_to_zar", fxToZar.trim());
      formData.append("factory_invoice_number", factoryBill.invoice_number.trim());
      formData.append("factory_amount", factoryBill.amount.trim());
      formData.append("factory_currency", factoryBill.currency.trim());
      formData.append("factory_file", factoryBill.file as File);
      formData.append("freight_invoice_number", freightBill.invoice_number.trim());
      formData.append("freight_amount", freightBill.amount.trim());
      formData.append("freight_currency", freightBill.currency.trim());
      formData.append("freight_file", freightBill.file as File);
      formData.append("clearance_invoice_number", clearanceBill.invoice_number.trim());
      formData.append("clearance_amount", clearanceBill.amount.trim());
      formData.append("clearance_currency", clearanceBill.currency.trim());
      formData.append("clearance_file", clearanceBill.file as File);
      const updated = await landPurchaseOrder(order.id, formData);
      setOrder(updated);
      setLandOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to land costs.");
    } finally {
      setActionLoading(false);
    }
  }

  function applyOrder(updated: PurchaseOrder) {
    setOrder(updated);
    setDraftLines(draftsFromOrder(updated));
    setSupplierRef(updated.supplier_ref ?? "");
    setHeaderNotes(updated.notes ?? "");
  }

  function updateDraft(key: string, patch: Partial<DraftLine>) {
    setDraftLines((current) =>
      current.map((line) => (line.key === key ? { ...line, ...patch } : line)),
    );
  }

  function addDraftLine() {
    setDraftLines((current) => [
      ...current,
      {
        key: `new-${current.length}-${Date.now()}`,
        sku_id: "",
        supplier_code: "",
        description: "",
        notes: "",
        qty: "",
        factory_unit_amount: "",
      },
    ]);
  }

  function removeDraftLine(key: string) {
    setDraftLines((current) => (current.length > 1 ? current.filter((line) => line.key !== key) : current));
  }

  const draftsValid = draftLines.every(
    (line) =>
      (line.sku_id || line.description.trim()) &&
      typeof line.qty === "number" &&
      line.qty > 0 &&
      line.factory_unit_amount.trim() !== "",
  );

  async function handleSaveLines() {
    if (!order || !draftsValid) {
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const updated = await updatePurchaseOrderLines(order.id, {
        supplier_ref: supplierRef.trim() || null,
        notes: headerNotes.trim() || null,
        lines: draftLines.map((line) => ({
          id: line.id,
          sku_id: line.sku_id || null,
          supplier_code: line.supplier_code.trim() || null,
          description: line.description.trim() || null,
          notes: line.notes.trim() || null,
          qty: line.qty as number,
          factory_unit_amount: line.factory_unit_amount.trim(),
        })),
      });
      applyOrder(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save the lines.");
    } finally {
      setActionLoading(false);
    }
  }

  function openSkuModal(line: DraftLine) {
    if (!line.id) {
      setError("Save the line first, then create its SKU.");
      return;
    }
    setSkuLineKey(line.key);
    setSkuDraft(skuDefaults(line));
    setSkuOpen(true);
  }

  const skuDraftValid =
    skuDraft.our_ref.trim() &&
    skuDraft.our_barcode.trim() &&
    skuDraft.name.trim() &&
    skuDraft.design.trim() &&
    skuDraft.fabric.trim();

  async function handleCreateSku() {
    if (!order || !skuLineKey || !skuDraftValid) {
      return;
    }
    const line = draftLines.find((entry) => entry.key === skuLineKey);
    if (!line?.id) {
      setError("Save the line first, then create its SKU.");
      return;
    }
    setActionLoading(true);
    setError(null);
    try {
      const updated = await createPurchaseOrderLineSku(order.id, line.id, {
        our_ref: skuDraft.our_ref.trim(),
        our_barcode: skuDraft.our_barcode.trim(),
        name: skuDraft.name.trim(),
        design: skuDraft.design.trim(),
        fabric: skuDraft.fabric.trim(),
      });
      applyOrder(updated);
      setSkuOpen(false);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError(err instanceof Error ? err.message : "Failed to create the SKU.");
      }
    } finally {
      setActionLoading(false);
    }
  }

  function renderBillSection(
    label: string,
    bill: BillForm,
    setBill: (value: BillForm) => void,
    fileKey: string,
  ) {
    return (
      <Stack gap={4}>
        <p className="cds--type-productive-heading-02">{label}</p>
        <TextInput
          id={`${fileKey}-invoice`}
          labelText="Invoice number"
          value={bill.invoice_number}
          onChange={(event) => setBill({ ...bill, invoice_number: event.target.value })}
          required
        />
        <TextInput
          id={`${fileKey}-amount`}
          labelText="Amount"
          value={bill.amount}
          onChange={(event) => setBill({ ...bill, amount: event.target.value })}
          required
        />
        <TextInput
          id={`${fileKey}-currency`}
          labelText="Currency"
          value={bill.currency}
          onChange={(event) => setBill({ ...bill, currency: event.target.value })}
          required
        />
        <div>
          <p className="cds--label">PDF</p>
          <FileUploaderDropContainer
            accept={["application/pdf", ".pdf"]}
            labelText="Upload PDF"
            multiple={false}
            onAddFiles={(_, { addedFiles }) => {
              const file = addedFiles[0];
              if (file && !file.invalidFileType) {
                setBill({ ...bill, file });
              }
            }}
          />
          {bill.file ? (
            <FileUploaderItem
              name={bill.file.name}
              status="complete"
              onDelete={() => setBill({ ...bill, file: null })}
            />
          ) : null}
        </div>
      </Stack>
    );
  }

  if (loading) {
    return <p className="cds--type-body-01">Loading purchase order…</p>;
  }

  if (!order) {
    return (
      <InlineNotification
        kind="error"
        title="Not found"
        subtitle="Purchase order could not be loaded."
        hideCloseButton
        lowContrast
      />
    );
  }

  const poWorkflowOpen =
    order.status !== "pending_approval" && order.status !== "rejected";
  const editing = order.status === "pending_approval" && canEditLines;
  const missingSkus = order.needs_sku_count;

  return (
    <Stack gap={6}>
      <div>
        <Button kind="ghost" size="sm" onClick={() => router.push("/purchase-orders")}>
          ← Back to purchase orders
        </Button>
        <h1 className="cds--type-productive-heading-04" style={{ marginTop: "0.5rem" }}>
          {order.po_number}
        </h1>
        <p className="cds--type-body-01">
          {order.supplier_name} · {PO_STATUS_LABELS[order.status]}
        </p>
        {order.supplier_ref ? (
          <p className="cds--type-body-01">Supplier reference {order.supplier_ref}</p>
        ) : null}
        {order.notes ? <p className="cds--type-body-01">{order.notes}</p> : null}
        {order.status !== "rejected" ? (
          <div style={{ marginTop: "1rem" }}>
            <Button
              kind="secondary"
              disabled={actionLoading}
              onClick={() => void handleDownloadPurchaseOrder()}
            >
              Download purchase order
            </Button>
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

      {missingSkus > 0 ? (
        <InlineNotification
          kind="warning"
          title="Needs SKUs"
          subtitle={`${missingSkus} ${missingSkus === 1 ? "line still needs" : "lines still need"} a SKU. Approve stays off until each highlighted line has one.`}
          hideCloseButton
          lowContrast
        />
      ) : null}

      {order.status === "pending_approval" && canApprovePo ? (
        <Stack gap={4} orientation="horizontal">
          <Button
            disabled={actionLoading || missingSkus > 0}
            onClick={() => void handleApprove()}
          >
            Approve
          </Button>
          <Button
            kind="danger--tertiary"
            disabled={actionLoading}
            onClick={() => void handleReject()}
          >
            Reject
          </Button>
        </Stack>
      ) : null}

      {poWorkflowOpen ? (
        <>
          <Stack gap={4} orientation="horizontal">
            <Button
              kind="secondary"
              disabled={actionLoading}
              onClick={() => void handleDownload()}
            >
              Download packing sheet
            </Button>
            {canRaise && order.status === "open" ? (
              <Button disabled={actionLoading} onClick={() => void handleMarkOnWater()}>
                Mark on water
              </Button>
            ) : null}
            {canRaise && order.status === "on_water" ? (
              <Button disabled={actionLoading} onClick={openLandModal}>
                Land costs
              </Button>
            ) : null}
            {canRecv && order.status === "landed" ? (
              <Button
                kind="primary"
                disabled={actionLoading}
                onClick={() => router.push(`/receive?po=${order.id}`)}
              >
                Receive
              </Button>
            ) : null}
          </Stack>
          <p className="cds--type-helper-text-01">
            Download or print. The app does not send email.
          </p>
        </>
      ) : null}

      {editing ? (
        <Stack gap={5}>
          <TextInput
            id="po-edit-supplier-ref"
            labelText="Supplier reference"
            value={supplierRef}
            onChange={(event) => setSupplierRef(event.target.value)}
          />
          <TextArea
            id="po-edit-notes"
            labelText="Notes"
            value={headerNotes}
            onChange={(event) => setHeaderNotes(event.target.value)}
          />
          <TableContainer title="Lines" description="Fill in a SKU, or create one, before approval">
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeader>SKU</TableHeader>
                  <TableHeader>Supplier code</TableHeader>
                  <TableHeader>Description</TableHeader>
                  <TableHeader>Fabric / finish</TableHeader>
                  <TableHeader>Qty</TableHeader>
                  <TableHeader>Factory unit</TableHeader>
                  <TableHeader>Notes</TableHeader>
                  <TableHeader></TableHeader>
                </TableRow>
              </TableHead>
              <TableBody>
                {draftLines.map((line) => (
                  <TableRow
                    key={line.key}
                    style={line.sku_id ? undefined : { background: "var(--cds-highlight)" }}
                  >
                    <TableCell>
                      <Select
                        id={`edit-sku-${line.key}`}
                        labelText="SKU"
                        hideLabel
                        value={line.sku_id}
                        onChange={(event) => onDraftSkuPicked(line.key, event.target.value)}
                      >
                        <SelectItem value="" text="No SKU yet" />
                        {skus.map((sku) => (
                          <SelectItem
                            key={sku.id}
                            value={sku.id}
                            text={`${sku.our_ref} — ${sku.name}`}
                          />
                        ))}
                      </Select>
                    </TableCell>
                    <TableCell>
                      <TextInput
                        id={`edit-code-${line.key}`}
                        labelText="Supplier code"
                        hideLabel
                        value={line.supplier_code}
                        onChange={(event) =>
                          updateDraft(line.key, { supplier_code: event.target.value })
                        }
                      />
                    </TableCell>
                    <TableCell>
                      <TextInput
                        id={`edit-desc-${line.key}`}
                        labelText="Description"
                        hideLabel
                        value={line.description}
                        onChange={(event) =>
                          updateDraft(line.key, { description: event.target.value })
                        }
                      />
                    </TableCell>
                    <TableCell>
                      {displayFabric(
                        skus.find((sku) => sku.id === line.sku_id)?.fabric ??
                          order.lines.find((row) => row.id === line.id)?.fabric,
                      ) ?? ""}
                    </TableCell>
                    <TableCell>
                      <NumberInput
                        id={`edit-qty-${line.key}`}
                        label="Qty"
                        hideLabel
                        min={1}
                        value={line.qty}
                        onChange={(_, { value }) =>
                          updateDraft(line.key, { qty: value === "" ? "" : Number(value) })
                        }
                      />
                    </TableCell>
                    <TableCell>
                      <TextInput
                        id={`edit-price-${line.key}`}
                        labelText="Factory unit"
                        hideLabel
                        value={line.factory_unit_amount}
                        onChange={(event) =>
                          updateDraft(line.key, { factory_unit_amount: event.target.value })
                        }
                      />
                    </TableCell>
                    <TableCell>
                      <TextInput
                        id={`edit-notes-${line.key}`}
                        labelText="Notes"
                        hideLabel
                        value={line.notes}
                        onChange={(event) => updateDraft(line.key, { notes: event.target.value })}
                      />
                    </TableCell>
                    <TableCell>
                      <div style={{ display: "flex", gap: "0.25rem" }}>
                        {!line.sku_id ? (
                          <Button
                            kind="tertiary"
                            size="sm"
                            disabled={actionLoading}
                            onClick={() => openSkuModal(line)}
                          >
                            Create SKU
                          </Button>
                        ) : null}
                        <Button
                          kind="ghost"
                          size="sm"
                          disabled={draftLines.length < 2}
                          onClick={() => removeDraftLine(line.key)}
                        >
                          Remove
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
          <Stack gap={4} orientation="horizontal">
            <Button kind="ghost" onClick={addDraftLine}>
              Add line
            </Button>
            <Button disabled={actionLoading || !draftsValid} onClick={() => void handleSaveLines()}>
              {actionLoading ? "Saving…" : "Save lines"}
            </Button>
          </Stack>
        </Stack>
      ) : (
      <TableContainer title="Lines" description="PO line items">
        <Table>
          <TableHead>
            <TableRow>
              <TableHeader>Our ref</TableHeader>
              <TableHeader>Supplier code</TableHeader>
              <TableHeader>Description</TableHeader>
              <TableHeader>Name</TableHeader>
              <TableHeader>Fabric / finish</TableHeader>
              <TableHeader>Qty</TableHeader>
              <TableHeader>Factory unit</TableHeader>
              <TableHeader>Unit cost ZAR</TableHeader>
            </TableRow>
          </TableHead>
          <TableBody>
            {order.lines.map((line) => (
              <TableRow
                key={line.id}
                style={line.needs_sku ? { background: "var(--cds-highlight)" } : undefined}
              >
                <TableCell>{line.our_ref ?? "—"}</TableCell>
                <TableCell>{line.supplier_code ?? "—"}</TableCell>
                <TableCell>{line.description ?? line.name}</TableCell>
                <TableCell>{line.name}</TableCell>
                <TableCell>{displayFabric(line.fabric) ?? ""}</TableCell>
                <TableCell>{line.qty}</TableCell>
                <TableCell>{line.factory_unit_amount}</TableCell>
                <TableCell>{line.unit_cost_zar ?? "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      )}

      {order.bills.length > 0 ? (
        <TableContainer title="Landing bills" description="Factory, freight, and clearance">
          <Table>
            <TableHead>
              <TableRow>
                <TableHeader>Kind</TableHeader>
                <TableHeader>Invoice number</TableHeader>
                <TableHeader>Amount</TableHeader>
                <TableHeader>Currency</TableHeader>
              </TableRow>
            </TableHead>
            <TableBody>
              {order.bills.map((bill, index) => (
                <TableRow key={`${bill.kind}-${index}`}>
                  <TableCell>{bill.kind}</TableCell>
                  <TableCell>{bill.invoice_number}</TableCell>
                  <TableCell>{bill.amount}</TableCell>
                  <TableCell>{bill.currency}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : null}

      <Modal
        open={skuOpen}
        modalHeading="Create a SKU"
        primaryButtonText={actionLoading ? "Saving…" : "Create SKU"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={actionLoading || !skuDraftValid}
        onRequestClose={() => setSkuOpen(false)}
        onRequestSubmit={() => void handleCreateSku()}
      >
        <Stack gap={4}>
          <TextInput
            id="line-sku-ref"
            labelText="Our ref"
            value={skuDraft.our_ref}
            onChange={(event) => setSkuDraft({ ...skuDraft, our_ref: event.target.value })}
          />
          <TextInput
            id="line-sku-barcode"
            labelText="Our barcode"
            helperText="Prefilled like a catalogue import. Change it if you have the real barcode."
            value={skuDraft.our_barcode}
            onChange={(event) => setSkuDraft({ ...skuDraft, our_barcode: event.target.value })}
          />
          <TextInput
            id="line-sku-name"
            labelText="Name"
            value={skuDraft.name}
            onChange={(event) => setSkuDraft({ ...skuDraft, name: event.target.value })}
          />
          <TextInput
            id="line-sku-design"
            labelText="Design"
            value={skuDraft.design}
            onChange={(event) => setSkuDraft({ ...skuDraft, design: event.target.value })}
          />
          <TextInput
            id="line-sku-fabric"
            labelText="Fabric"
            value={skuDraft.fabric}
            onChange={(event) => setSkuDraft({ ...skuDraft, fabric: event.target.value })}
          />
        </Stack>
      </Modal>

      <Modal
        open={landOpen}
        modalHeading="Land costs"
        primaryButtonText={actionLoading ? "Landing…" : "Land"}
        secondaryButtonText="Cancel"
        primaryButtonDisabled={actionLoading || !landValid}
        onRequestClose={() => setLandOpen(false)}
        onRequestSubmit={() => void handleLand()}
        size="lg"
      >
        <Stack gap={6}>
          <TextInput
            id="land-fx"
            labelText="FX to ZAR"
            helperText="ZAR per 1 unit of foreign currency"
            value={fxToZar}
            onChange={(event) => setFxToZar(event.target.value)}
            required
          />
          {renderBillSection("Factory", factoryBill, setFactoryBill, "factory")}
          {renderBillSection("Freight", freightBill, setFreightBill, "freight")}
          {renderBillSection("Clearance", clearanceBill, setClearanceBill, "clearance")}
        </Stack>
      </Modal>
    </Stack>
  );
}

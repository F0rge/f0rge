"use client";

import {
  Button,
  DataTable,
  InlineNotification,
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
import { useEffect, useState } from "react";

import {
  ApiError,
  displayPrice,
  exVatToIncVat,
  formatPriceAmount,
  incVatToExVat,
  listCostAudit,
  listSuppliers,
  parsePriceInput,
  updateSku,
  type Sku,
  type SkuLeadTimeRow,
  type Supplier,
  type UnitCostAuditEntry,
  type UpdateSkuPricePayload,
} from "@/lib/api";
import { formatObservedMedianLine } from "@/lib/lead-times";

type PriceBasis = "ex" | "inc";

type EditorFormState = {
  wholesaleEx: string;
  wholesaleInc: string;
  retailEx: string;
  retailInc: string;
  lastEditedWholesale: PriceBasis | null;
  lastEditedRetail: PriceBasis | null;
  preferredSupplierId: string;
  supplierRef: string;
  leadTimeDays: string;
  madeToOrderCapacity: string;
  madeToOrderMinDays: string;
  madeToOrderMaxDays: string;
  madeToOrderExpiresAt: string;
  reorderMin: string;
};

type SkuPriceEditorProps = {
  sku: Sku | null;
  open: boolean;
  readOnly: boolean;
  showCostAudit: boolean;
  unitCostZar: string | null;
  observedLeadTime?: Pick<SkuLeadTimeRow, "median_days" | "n"> | null;
  saving: boolean;
  onSavingChange: (saving: boolean) => void;
  onClose: () => void;
  onSaved: () => Promise<void>;
  onError: (message: string) => void;
  /** When true, renders as an embeddable section (no close/cancel chrome). */
  embedded?: boolean;
};

const COST_AUDIT_HEADERS = [
  { key: "created_at", header: "Date" },
  { key: "source", header: "Source" },
  { key: "new_cost_zar", header: "New cost (ZAR)" },
  { key: "location_name", header: "Location" },
] as const;

const emptyForm: EditorFormState = {
  wholesaleEx: "",
  wholesaleInc: "",
  retailEx: "",
  retailInc: "",
  lastEditedWholesale: null,
  lastEditedRetail: null,
  preferredSupplierId: "",
  supplierRef: "",
  leadTimeDays: "",
  madeToOrderCapacity: "",
  madeToOrderMinDays: "",
  madeToOrderMaxDays: "",
  madeToOrderExpiresAt: "",
  reorderMin: "",
};

function localDateTimeInput(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "";
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

function formFromSku(sku: Sku): EditorFormState {
  return {
    wholesaleEx: sku.wholesale_ex_vat ?? "",
    wholesaleInc: sku.wholesale_inc_vat ?? "",
    retailEx: sku.retail_ex_vat ?? "",
    retailInc: sku.retail_inc_vat ?? "",
    lastEditedWholesale: null,
    lastEditedRetail: null,
    preferredSupplierId: sku.preferred_supplier_id ?? "",
    supplierRef: sku.supplier_ref ?? "",
    leadTimeDays: sku.lead_time_days !== null ? String(sku.lead_time_days) : "",
    madeToOrderCapacity: sku.made_to_order_capacity !== null ? String(sku.made_to_order_capacity) : "",
    madeToOrderMinDays: sku.made_to_order_lead_time_min_days !== null ? String(sku.made_to_order_lead_time_min_days) : "",
    madeToOrderMaxDays: sku.made_to_order_lead_time_max_days !== null ? String(sku.made_to_order_lead_time_max_days) : "",
    madeToOrderExpiresAt: localDateTimeInput(sku.made_to_order_expires_at),
    reorderMin: sku.reorder_min !== null ? String(sku.reorder_min) : "",
  };
}

function parseLeadTimeDays(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed) || !Number.isInteger(parsed) || parsed < 0) {
    return null;
  }
  return parsed;
}

function parseReorderMin(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed) || !Number.isInteger(parsed) || parsed < 1) {
    return null;
  }
  return parsed;
}

function parseWholeNumber(value: string, minimum: number): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  return Number.isSafeInteger(parsed) && parsed >= minimum ? parsed : null;
}

function madeToOrderFormError(form: EditorFormState): string | null {
  const values = [form.madeToOrderCapacity, form.madeToOrderMinDays, form.madeToOrderMaxDays, form.madeToOrderExpiresAt];
  if (values.every((value) => !value.trim())) return null;
  if (values.some((value) => !value.trim())) return "Set the allowance, both lead-time bounds, and expiry together.";
  const capacity = parseWholeNumber(form.madeToOrderCapacity, 0);
  const minDays = parseWholeNumber(form.madeToOrderMinDays, 1);
  const maxDays = parseWholeNumber(form.madeToOrderMaxDays, 1);
  const expiry = new Date(form.madeToOrderExpiresAt);
  if (capacity === null || minDays === null || maxDays === null) return "Use whole numbers for the allowance and lead-time bounds.";
  if (maxDays < minDays) return "Maximum lead time must be at least the minimum.";
  if (!Number.isFinite(expiry.getTime()) || expiry.getTime() <= Date.now()) return "Choose a future expiry time.";
  return null;
}

function madeToOrderFormChanged(sku: Sku, form: EditorFormState): boolean {
  return form.madeToOrderCapacity.trim() !== (sku.made_to_order_capacity === null ? "" : String(sku.made_to_order_capacity)) ||
    form.madeToOrderMinDays.trim() !== (sku.made_to_order_lead_time_min_days === null ? "" : String(sku.made_to_order_lead_time_min_days)) ||
    form.madeToOrderMaxDays.trim() !== (sku.made_to_order_lead_time_max_days === null ? "" : String(sku.made_to_order_lead_time_max_days)) ||
    form.madeToOrderExpiresAt !== localDateTimeInput(sku.made_to_order_expires_at);
}

function buildPayload(sku: Sku, form: EditorFormState): UpdateSkuPricePayload {
  const payload: UpdateSkuPricePayload = {};

  if (form.lastEditedWholesale === "ex") {
    payload.wholesale_ex_vat = form.wholesaleEx.trim() || null;
  } else if (form.lastEditedWholesale === "inc") {
    payload.wholesale_inc_vat = form.wholesaleInc.trim() || null;
  }

  if (form.lastEditedRetail === "ex") {
    payload.retail_ex_vat = form.retailEx.trim() || null;
  } else if (form.lastEditedRetail === "inc") {
    payload.retail_inc_vat = form.retailInc.trim() || null;
  }

  const preferredSupplierId = form.preferredSupplierId.trim();
  if (preferredSupplierId !== (sku.preferred_supplier_id ?? "")) {
    payload.preferred_supplier_id = preferredSupplierId || null;
  }

  const supplierRef = form.supplierRef.trim();
  if (supplierRef !== (sku.supplier_ref ?? "")) {
    payload.supplier_ref = supplierRef || null;
  }

  const leadTimeDays = parseLeadTimeDays(form.leadTimeDays);
  if (leadTimeDays !== sku.lead_time_days) {
    payload.lead_time_days = leadTimeDays;
  }

  const reorderMin = parseReorderMin(form.reorderMin);
  if (reorderMin !== sku.reorder_min) {
    payload.reorder_min = reorderMin;
  }

  if (madeToOrderFormChanged(sku, form)) {
    const disabled = !form.madeToOrderCapacity.trim() && !form.madeToOrderMinDays.trim() &&
      !form.madeToOrderMaxDays.trim() && !form.madeToOrderExpiresAt.trim();
    payload.made_to_order_capacity = disabled ? null : parseWholeNumber(form.madeToOrderCapacity, 0);
    payload.made_to_order_lead_time_min_days = disabled ? null : parseWholeNumber(form.madeToOrderMinDays, 1);
    payload.made_to_order_lead_time_max_days = disabled ? null : parseWholeNumber(form.madeToOrderMaxDays, 1);
    payload.made_to_order_expires_at = disabled ? null : new Date(form.madeToOrderExpiresAt).toISOString();
  }

  return payload;
}

function hasFormEdits(sku: Sku, form: EditorFormState): boolean {
  if (form.lastEditedWholesale !== null || form.lastEditedRetail !== null) {
    return true;
  }
  if (form.preferredSupplierId.trim() !== (sku.preferred_supplier_id ?? "")) {
    return true;
  }
  if (form.supplierRef.trim() !== (sku.supplier_ref ?? "")) {
    return true;
  }
  if (parseLeadTimeDays(form.leadTimeDays) !== sku.lead_time_days) {
    return true;
  }
  if (parseReorderMin(form.reorderMin) !== sku.reorder_min) {
    return true;
  }
  return madeToOrderFormChanged(sku, form);
}

export function SkuPriceEditor({
  sku,
  open,
  readOnly,
  showCostAudit,
  unitCostZar,
  observedLeadTime = null,
  saving,
  onSavingChange,
  onClose,
  onSaved,
  onError,
  embedded = false,
}: SkuPriceEditorProps) {
  const [form, setForm] = useState<EditorFormState>(emptyForm);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [costAudit, setCostAudit] = useState<UnitCostAuditEntry[]>([]);
  const [costAuditLoading, setCostAuditLoading] = useState(false);

  useEffect(() => {
    if (sku && (open || embedded)) {
      setForm(formFromSku(sku));
    }
    if (!open && !embedded) {
      setForm(emptyForm);
      setCostAudit([]);
    }
  }, [sku, open, embedded]);

  useEffect(() => {
    if ((!open && !embedded) || readOnly) {
      return;
    }
    let cancelled = false;
    listSuppliers()
      .then((data) => {
        if (!cancelled) {
          setSuppliers(data);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSuppliers([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [open, embedded, readOnly]);

  useEffect(() => {
    if ((!open && !embedded) || !sku || !showCostAudit) {
      return;
    }
    let cancelled = false;
    setCostAuditLoading(true);
    listCostAudit(sku.id)
      .then((rows) => {
        if (!cancelled) {
          setCostAudit(rows);
        }
      })
      .catch((err) => {
        if (!cancelled && err instanceof ApiError && err.status === 403) {
          setCostAudit([]);
        } else if (!cancelled) {
          setCostAudit([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setCostAuditLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [open, embedded, sku, showCostAudit]);

  function updateWholesaleEx(value: string) {
    setForm((current) => {
      const parsed = parsePriceInput(value);
      return {
        ...current,
        wholesaleEx: value,
        wholesaleInc: parsed === null ? "" : formatPriceAmount(exVatToIncVat(parsed)),
        lastEditedWholesale: "ex",
      };
    });
  }

  function updateWholesaleInc(value: string) {
    setForm((current) => {
      const parsed = parsePriceInput(value);
      return {
        ...current,
        wholesaleInc: value,
        wholesaleEx: parsed === null ? "" : formatPriceAmount(incVatToExVat(parsed)),
        lastEditedWholesale: "inc",
      };
    });
  }

  function updateRetailEx(value: string) {
    setForm((current) => {
      const parsed = parsePriceInput(value);
      return {
        ...current,
        retailEx: value,
        retailInc: parsed === null ? "" : formatPriceAmount(exVatToIncVat(parsed)),
        lastEditedRetail: "ex",
      };
    });
  }

  function updateRetailInc(value: string) {
    setForm((current) => {
      const parsed = parsePriceInput(value);
      return {
        ...current,
        retailInc: value,
        retailEx: parsed === null ? "" : formatPriceAmount(incVatToExVat(parsed)),
        lastEditedRetail: "inc",
      };
    });
  }

  const hasEdits = sku ? hasFormEdits(sku, form) : false;
  const madeToOrderError = readOnly ? null : madeToOrderFormError(form);
  const invalidMadeToOrderEdit = !!sku && madeToOrderFormChanged(sku, form) && madeToOrderError !== null;

  async function handleSave() {
    if (!sku || readOnly) {
      return;
    }
    const payload = buildPayload(sku, form);
    if (Object.keys(payload).length === 0) {
      if (!embedded) {
        onClose();
      }
      return;
    }

    onSavingChange(true);
    try {
      await updateSku(sku.id, payload);
      if (!embedded) {
        onClose();
      }
      await onSaved();
    } catch (err) {
      if (err instanceof ApiError) {
        onError(err.message);
      } else {
        onError(err instanceof Error ? err.message : "Failed to save prices.");
      }
    } finally {
      onSavingChange(false);
    }
  }

  if ((!open && !embedded) || !sku) {
    return null;
  }

  const costAuditRows = costAudit.map((entry) => ({
    id: entry.id,
    created_at: new Date(entry.created_at).toLocaleDateString("en-ZA"),
    source: entry.source,
    new_cost_zar: entry.new_cost_zar,
    location_name: entry.location_name ?? "—",
  }));

  const preferredSupplierLabel =
    sku.preferred_supplier_name ??
    suppliers.find((entry) => entry.id === form.preferredSupplierId)?.name ??
    "—";

  return (
    <section
      className={embedded ? undefined : "cds--layer-01"}
      style={
        embedded
          ? undefined
          : {
              padding: "1.5rem",
              border: "1px solid var(--cds-border-subtle-01, #e0e0e0)",
              maxWidth: "48rem",
            }
      }
      aria-labelledby={embedded ? undefined : "sku-price-editor-heading"}
    >
      <Stack gap={5}>
        {!embedded ? (
          <div>
            <h2 id="sku-price-editor-heading" className="cds--type-productive-heading-03">
              {readOnly ? "SKU prices" : "Edit prices"}
            </h2>
            <p className="cds--type-body-01">
              <strong>{sku.our_ref}</strong> — {sku.name}
            </p>
          </div>
        ) : null}
        {showCostAudit && unitCostZar ? (
          <InlineNotification
            kind="info"
            title="Unit cost"
            subtitle={`Landed unit cost from inventory: ${displayPrice(unitCostZar)} ZAR`}
            hideCloseButton
            lowContrast
          />
        ) : null}
        {showCostAudit ? (
          <TextInput
            id="sku-last-landed-cost"
            labelText="Last landed cost"
            value={
              sku.last_landed_cost_zar
                ? `${displayPrice(sku.last_landed_cost_zar)} ZAR`
                : "—"
            }
            readOnly
          />
        ) : null}
        {readOnly ? (
          <>
            <TextInput
              id="sku-preferred-supplier-readonly"
              labelText="Preferred supplier"
              value={preferredSupplierLabel}
              readOnly
            />
            <TextInput
              id="sku-supplier-ref-readonly"
              labelText="Supplier ref"
              value={form.supplierRef || "—"}
              readOnly
            />
            <TextInput
              id="sku-lead-time-readonly"
              labelText="Lead time (days)"
              value={form.leadTimeDays ? `${form.leadTimeDays} days` : "—"}
              readOnly
            />
            <TextInput
              id="sku-observed-lead-time-readonly"
              labelText="Observed median"
              value={formatObservedMedianLine(observedLeadTime ?? undefined)}
              readOnly
            />
            <TextInput
              id="sku-reorder-min-readonly"
              labelText="Reorder min"
              value={form.reorderMin || "—"}
              readOnly
            />
            <TextInput
              id="sku-made-to-order-readonly"
              labelText="Made-to-order allowance"
              value={sku.made_to_order_capacity === null ? "—" : `${sku.made_to_order_capacity} units`}
              readOnly
            />
            <TextInput
              id="sku-made-to-order-lead-time-readonly"
              labelText="Confirmed made-to-order lead time"
              value={sku.made_to_order_lead_time_min_days === null || sku.made_to_order_lead_time_max_days === null
                ? "—" : `${sku.made_to_order_lead_time_min_days}–${sku.made_to_order_lead_time_max_days} days`}
              readOnly
            />
            <TextInput
              id="sku-made-to-order-expiry-readonly"
              labelText="Made-to-order offer expiry"
              value={sku.made_to_order_expires_at ? new Date(sku.made_to_order_expires_at).toLocaleString("en-ZA") : "—"}
              readOnly
            />
          </>
        ) : (
          <>
            <Select
              id="sku-preferred-supplier"
              labelText="Preferred supplier"
              value={form.preferredSupplierId}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  preferredSupplierId: event.target.value,
                }))
              }
            >
              <SelectItem value="" text="None" />
              {suppliers.map((entry) => (
                <SelectItem key={entry.id} value={entry.id} text={entry.name} />
              ))}
            </Select>
            <TextInput
              id="sku-supplier-ref"
              labelText="Supplier ref"
              helperText="Supplier's reference — not our barcode"
              value={form.supplierRef}
              onChange={(event) =>
                setForm((current) => ({ ...current, supplierRef: event.target.value }))
              }
            />
            <TextInput
              id="sku-lead-time-days"
              labelText="Lead time (days)"
              helperText="Leave blank for none"
              value={form.leadTimeDays}
              onChange={(event) =>
                setForm((current) => ({ ...current, leadTimeDays: event.target.value }))
              }
            />
            <TextInput
              id="sku-observed-lead-time"
              labelText="Observed median"
              helperText="From completed POs — not written to lead time"
              value={formatObservedMedianLine(observedLeadTime ?? undefined)}
              readOnly
            />
            <TextInput
              id="sku-reorder-min"
              labelText="Reorder min"
              helperText="Minimum stock level; leave blank to clear"
              value={form.reorderMin}
              onChange={(event) =>
                setForm((current) => ({ ...current, reorderMin: event.target.value }))
              }
            />
            <TextInput
              id="sku-made-to-order-capacity"
              type="number"
              min={0}
              step={1}
              labelText="Made-to-order allowance (units)"
              helperText="Finite quantity available after physical stock is gone. Changing the allowance starts a new allocation."
              value={form.madeToOrderCapacity}
              onChange={(event) => setForm((current) => ({ ...current, madeToOrderCapacity: event.target.value }))}
            />
            <TextInput
              id="sku-made-to-order-min-days"
              type="number"
              min={1}
              step={1}
              labelText="Minimum lead time (days)"
              value={form.madeToOrderMinDays}
              onChange={(event) => setForm((current) => ({ ...current, madeToOrderMinDays: event.target.value }))}
            />
            <TextInput
              id="sku-made-to-order-max-days"
              type="number"
              min={1}
              step={1}
              labelText="Maximum lead time (days)"
              value={form.madeToOrderMaxDays}
              onChange={(event) => setForm((current) => ({ ...current, madeToOrderMaxDays: event.target.value }))}
            />
            <TextInput
              id="sku-made-to-order-expires-at"
              type="datetime-local"
              labelText="Made-to-order offer expires"
              helperText="The offer must expire in the future. Clear all four fields to disable it."
              value={form.madeToOrderExpiresAt}
              onChange={(event) => setForm((current) => ({ ...current, madeToOrderExpiresAt: event.target.value }))}
            />
            {madeToOrderError && (madeToOrderFormChanged(sku, form) || madeToOrderError !== "Set the allowance, both lead-time bounds, and expiry together.") &&
              <InlineNotification kind="error" title="Made-to-order offer needs attention" subtitle={madeToOrderError} hideCloseButton lowContrast />}
          </>
        )}
        <TextInput
          id="sku-wholesale-ex-vat"
          labelText="Wholesale ex-VAT"
          helperText="VAT 15% — paired inc-VAT updates as you type"
          value={form.wholesaleEx}
          readOnly={readOnly}
          onChange={(event) => updateWholesaleEx(event.target.value)}
        />
        <TextInput
          id="sku-wholesale-inc-vat"
          labelText="Wholesale inc-VAT"
          value={form.wholesaleInc}
          readOnly={readOnly}
          onChange={(event) => updateWholesaleInc(event.target.value)}
        />
        <TextInput
          id="sku-retail-ex-vat"
          labelText="Retail ex-VAT"
          helperText="VAT 15% — paired inc-VAT updates as you type"
          value={form.retailEx}
          readOnly={readOnly}
          onChange={(event) => updateRetailEx(event.target.value)}
        />
        <TextInput
          id="sku-retail-inc-vat"
          labelText="Retail inc-VAT"
          value={form.retailInc}
          readOnly={readOnly}
          onChange={(event) => updateRetailInc(event.target.value)}
        />
        {showCostAudit ? (
          <div>
            <h3 className="cds--type-productive-heading-02">Cost history</h3>
            {costAuditLoading ? (
              <p className="cds--type-body-01">Loading cost history…</p>
            ) : costAuditRows.length === 0 ? null : (
              <DataTable rows={costAuditRows} headers={[...COST_AUDIT_HEADERS]}>
                {({ rows: tableRows, headers, getTableProps, getHeaderProps, getRowProps }) => (
                  <TableContainer title="Cost audit">
                    <Table {...getTableProps()} size="sm">
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
                        {tableRows.map((row) => (
                          <TableRow {...getRowProps({ row })} key={row.id}>
                            {row.cells.map((cell) => (
                              <TableCell key={cell.id}>{cell.value}</TableCell>
                            ))}
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                )}
              </DataTable>
            )}
          </div>
        ) : null}
        {!readOnly || !embedded ? (
          <div style={{ display: "flex", gap: "0.75rem" }}>
            {readOnly ? (
              embedded ? null : (
                <Button type="button" kind="secondary" onClick={onClose}>
                  Close
                </Button>
              )
            ) : (
              <>
                <Button
                  type="button"
                  disabled={saving || !hasEdits || invalidMadeToOrderEdit}
                  onClick={() => void handleSave()}
                >
                  {saving ? "Saving…" : "Save"}
                </Button>
                {!embedded ? (
                  <Button type="button" kind="secondary" disabled={saving} onClick={onClose}>
                    Cancel
                  </Button>
                ) : null}
              </>
            )}
          </div>
        ) : null}
      </Stack>
    </section>
  );
}

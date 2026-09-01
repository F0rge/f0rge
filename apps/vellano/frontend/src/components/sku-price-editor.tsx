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
  type Supplier,
  type UnitCostAuditEntry,
  type UpdateSkuPricePayload,
} from "@/lib/api";

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
};

type SkuPriceEditorProps = {
  sku: Sku | null;
  open: boolean;
  readOnly: boolean;
  showCostAudit: boolean;
  unitCostZar: string | null;
  saving: boolean;
  onSavingChange: (saving: boolean) => void;
  onClose: () => void;
  onSaved: () => Promise<void>;
  onError: (message: string) => void;
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
};

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
  return parseLeadTimeDays(form.leadTimeDays) !== sku.lead_time_days;
}

export function SkuPriceEditor({
  sku,
  open,
  readOnly,
  showCostAudit,
  unitCostZar,
  saving,
  onSavingChange,
  onClose,
  onSaved,
  onError,
}: SkuPriceEditorProps) {
  const [form, setForm] = useState<EditorFormState>(emptyForm);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [costAudit, setCostAudit] = useState<UnitCostAuditEntry[]>([]);
  const [costAuditLoading, setCostAuditLoading] = useState(false);

  useEffect(() => {
    if (sku && open) {
      setForm(formFromSku(sku));
    }
    if (!open) {
      setForm(emptyForm);
      setCostAudit([]);
    }
  }, [sku, open]);

  useEffect(() => {
    if (!open || readOnly) {
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
  }, [open, readOnly]);

  useEffect(() => {
    if (!open || !sku || !showCostAudit) {
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
  }, [open, sku, showCostAudit]);

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

  async function handleSave() {
    if (!sku || readOnly) {
      return;
    }
    const payload = buildPayload(sku, form);
    if (Object.keys(payload).length === 0) {
      onClose();
      return;
    }

    onSavingChange(true);
    try {
      await updateSku(sku.id, payload);
      onClose();
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

  if (!open || !sku) {
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
      className="cds--layer-01"
      style={{
        padding: "1.5rem",
        border: "1px solid var(--cds-border-subtle-01, #e0e0e0)",
        maxWidth: "48rem",
      }}
      aria-labelledby="sku-price-editor-heading"
    >
      <Stack gap={5}>
        <div>
          <h2 id="sku-price-editor-heading" className="cds--type-productive-heading-03">
            {readOnly ? "SKU prices" : "Edit prices"}
          </h2>
          <p className="cds--type-body-01">
            <strong>{sku.our_ref}</strong> — {sku.name}
          </p>
        </div>
        {unitCostZar ? (
          <InlineNotification
            kind="info"
            title="Unit cost"
            subtitle={`Landed unit cost from inventory: ${displayPrice(unitCostZar)} ZAR`}
            hideCloseButton
            lowContrast
          />
        ) : null}
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
        <div style={{ display: "flex", gap: "0.75rem" }}>
          {readOnly ? (
            <Button type="button" kind="secondary" onClick={onClose}>
              Close
            </Button>
          ) : (
            <>
              <Button
                type="button"
                disabled={saving || !hasEdits}
                onClick={() => void handleSave()}
              >
                {saving ? "Saving…" : "Save"}
              </Button>
              <Button type="button" kind="secondary" disabled={saving} onClick={onClose}>
                Cancel
              </Button>
            </>
          )}
        </div>
      </Stack>
    </section>
  );
}

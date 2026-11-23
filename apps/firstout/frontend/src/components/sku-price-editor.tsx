"use client";

import { Accordion, AccordionItem, Button, Checkbox, InlineNotification, Select, SelectItem, Stack, TextInput } from "@carbon/react";
import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { SkuInvoicePreview } from "@/components/sku-invoice-preview";
import { SkuPriceFields } from "@/components/sku-price-fields";
import { listSuppliers, updateSku, type Sku, type SkuLeadTimeRow, type UpdateSkuPricePayload } from "@/lib/api";
import { catalogueSaveFailure } from "@/lib/catalogue-editor";
import { formatObservedMedianLine } from "@/lib/lead-times";
import { formatZarAmount } from "@/lib/money";
import { referenceQueries } from "@/lib/queries";
import {
  buildSkuPriceChanges,
  skuPriceFormFromSku,
  validateSkuPriceForm,
  type SkuPriceErrors,
  type SkuPriceForm,
} from "@/lib/sku-price-form";

import styles from "./sku-price-editor.module.css";

type EditorFormState = {
  preferredSupplierId: string;
  supplierRef: string;
  leadTimeDays: string;
  madeToOrderCapacity: string;
  madeToOrderMinDays: string;
  madeToOrderMaxDays: string;
  madeToOrderExpiresAt: string;
  reorderMin: string;
  excludeFromCommission: boolean;
};

type SkuPriceEditorProps = {
  sku: Sku;
  active: boolean;
  readOnly: boolean;
  canViewCost: boolean;
  observedLeadTime?: Pick<SkuLeadTimeRow, "median_days" | "n"> | null;
  onSaved: (sku: Sku) => void;
  onError: (message: string | null) => void;
};

function localDateTimeInput(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return "";
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

function formFromSku(sku: Sku): EditorFormState {
  return {
    preferredSupplierId: sku.preferred_supplier_id ?? "",
    supplierRef: sku.supplier_ref ?? "",
    leadTimeDays: sku.lead_time_days !== null ? String(sku.lead_time_days) : "",
    madeToOrderCapacity: sku.made_to_order_capacity !== null ? String(sku.made_to_order_capacity) : "",
    madeToOrderMinDays: sku.made_to_order_lead_time_min_days !== null ? String(sku.made_to_order_lead_time_min_days) : "",
    madeToOrderMaxDays: sku.made_to_order_lead_time_max_days !== null ? String(sku.made_to_order_lead_time_max_days) : "",
    madeToOrderExpiresAt: localDateTimeInput(sku.made_to_order_expires_at),
    reorderMin: sku.reorder_min !== null ? String(sku.reorder_min) : "",
    excludeFromCommission: !!sku.exclude_from_commission,
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

function buildSettingsUpdate(sku: Sku, form: EditorFormState): UpdateSkuPricePayload {
  const payload: UpdateSkuPricePayload = {};

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

  if (form.excludeFromCommission !== !!sku.exclude_from_commission) {
    payload.exclude_from_commission = form.excludeFromCommission;
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

export function SkuPriceEditor({
  sku,
  active,
  readOnly,
  canViewCost,
  observedLeadTime,
  onSaved,
  onError,
}: SkuPriceEditorProps) {
  const [priceDraft, setPriceDraft] = useState<Partial<SkuPriceForm>>({});
  const [settingsDraft, setSettingsDraft] = useState<Partial<EditorFormState>>({});
  const [serverErrors, setServerErrors] = useState<SkuPriceErrors>({});
  const [saving, setSaving] = useState(false);
  const savingRef = useRef(false);
  const suppliersQuery = useQuery({
    queryKey: ["suppliers", "list"],
    queryFn: () => listSuppliers(),
    enabled: active && !readOnly,
  });
  const suppliers = suppliersQuery.data ?? [];
  const vatSettings = useQuery({ ...referenceQueries.settings, enabled: active });
  const vatRate = vatSettings.data?.vat_rate;

  const form = { ...formFromSku(sku), ...settingsDraft };
  const prices = { ...skuPriceFormFromSku(sku), ...priceDraft };
  const priceErrors = validateSkuPriceForm(prices, vatRate);
  const priceChanges = buildSkuPriceChanges(sku, prices);
  const invalidPrices = Object.keys(priceErrors).length > 0;
  const madeToOrderChanged = madeToOrderFormChanged(sku, form);
  const madeToOrderError = readOnly ? null : madeToOrderFormError(form);
  const invalidMadeToOrder = madeToOrderChanged && madeToOrderError !== null;
  const payload = invalidMadeToOrder ? {} : { ...buildSettingsUpdate(sku, form), ...priceChanges };
  const hasEdits = Object.keys(payload).length > 0;

  async function handleSave() {
    if (readOnly || savingRef.current || !hasEdits || invalidPrices || invalidMadeToOrder) return;

    savingRef.current = true;
    setSaving(true);
    setServerErrors({});
    onError(null);
    try {
      const updated = await updateSku(sku.id, payload);
      setPriceDraft({});
      setSettingsDraft({});
      onSaved(updated);
    } catch (error) {
      const failure = catalogueSaveFailure(error);
      setServerErrors(failure.fields);
      onError(failure.message);
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  }

  const preferredSupplierLabel =
    sku.preferred_supplier_name ??
    suppliers.find((entry) => entry.id === form.preferredSupplierId)?.name ??
    "—";

  return (
    <Stack gap={6}>
      <div className={styles.pricing}>
        <Stack gap={4}>
          <h2 className="cds--type-productive-heading-03">SKU prices</h2>
          {canViewCost && sku.average_unit_cost_zar != null && (
            <p className="cds--type-body-01">Average unit cost · {formatZarAmount(sku.average_unit_cost_zar)} excl. VAT</p>
          )}
          <SkuPriceFields
            idPrefix="sku-price"
            sku={sku}
            form={prices}
            errors={{ ...priceErrors, ...serverErrors }}
            vatRate={vatRate}
            retryVatRate={vatSettings.isLoadingError ? () => void vatSettings.refetch() : undefined}
            canViewCost={canViewCost}
            readOnly={readOnly}
            disabled={saving}
            onChange={(field, value) => {
              setPriceDraft((current) => ({ ...current, [field]: value }));
              setServerErrors((current) => ({ ...current, [field]: undefined }));
            }}
          />
        </Stack>
        <SkuInvoicePreview
          skuId={sku.id}
          skuRevision={sku.updated_at}
          active={active}
          vatRate={vatRate}
          priceChanges={invalidPrices ? null : priceChanges}
        />
      </div>
      <Accordion>
        <AccordionItem title="Supply &amp; ordering">
          <Stack gap={4}>
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
                  disabled={saving}
                  labelText="Preferred supplier"
                  value={form.preferredSupplierId}
                  onChange={(event) =>
                    setSettingsDraft((current) => ({
                      ...current,
                      preferredSupplierId: event.target.value,
                    }))
                  }
                >
                  <SelectItem value="" text="None" />
                  {sku.preferred_supplier_id && !suppliers.some((supplier) => supplier.id === sku.preferred_supplier_id) && (
                    <SelectItem value={sku.preferred_supplier_id} text={preferredSupplierLabel} />
                  )}
                  {suppliers.map((entry) => (
                    <SelectItem key={entry.id} value={entry.id} text={entry.name} />
                  ))}
                </Select>
                <TextInput
                  id="sku-supplier-ref"
                  disabled={saving}
                  labelText="Supplier ref"
                  helperText="Supplier's reference — not our barcode"
                  value={form.supplierRef}
                  onChange={(event) =>
                    setSettingsDraft((current) => ({ ...current, supplierRef: event.target.value }))
                  }
                />
                <TextInput
                  id="sku-lead-time-days"
                  disabled={saving}
                  labelText="Lead time (days)"
                  helperText="Leave blank for none"
                  value={form.leadTimeDays}
                  onChange={(event) =>
                    setSettingsDraft((current) => ({ ...current, leadTimeDays: event.target.value }))
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
                  disabled={saving}
                  labelText="Reorder min"
                  helperText="Minimum stock level; leave blank to clear"
                  value={form.reorderMin}
                  onChange={(event) =>
                    setSettingsDraft((current) => ({ ...current, reorderMin: event.target.value }))
                  }
                />
                <TextInput
                  id="sku-made-to-order-capacity"
                  disabled={saving}
                  type="number"
                  min={0}
                  step={1}
                  labelText="Made-to-order allowance (units)"
                  helperText="Finite quantity available after physical stock is gone. Changing the allowance starts a new allocation."
                  value={form.madeToOrderCapacity}
                  onChange={(event) => setSettingsDraft((current) => ({ ...current, madeToOrderCapacity: event.target.value }))}
                />
                <TextInput
                  id="sku-made-to-order-min-days"
                  disabled={saving}
                  type="number"
                  min={1}
                  step={1}
                  labelText="Minimum lead time (days)"
                  value={form.madeToOrderMinDays}
                  onChange={(event) => setSettingsDraft((current) => ({ ...current, madeToOrderMinDays: event.target.value }))}
                />
                <TextInput
                  id="sku-made-to-order-max-days"
                  disabled={saving}
                  type="number"
                  min={1}
                  step={1}
                  labelText="Maximum lead time (days)"
                  value={form.madeToOrderMaxDays}
                  onChange={(event) => setSettingsDraft((current) => ({ ...current, madeToOrderMaxDays: event.target.value }))}
                />
                <TextInput
                  id="sku-made-to-order-expires-at"
                  disabled={saving}
                  type="datetime-local"
                  labelText="Made-to-order offer expires"
                  helperText="The offer must expire in the future. Clear all four fields to disable it."
                  value={form.madeToOrderExpiresAt}
                  onChange={(event) => setSettingsDraft((current) => ({ ...current, madeToOrderExpiresAt: event.target.value }))}
                />
                {madeToOrderError && !invalidMadeToOrder && madeToOrderError !== "Set the allowance, both lead-time bounds, and expiry together." &&
                  <InlineNotification kind="error" title="Made-to-order offer needs attention" subtitle={madeToOrderError} hideCloseButton lowContrast />}
              </>
            )}
            <div>
              <h3 className="cds--type-productive-heading-02">Commission</h3>
              <Checkbox
                id="sku-exclude-from-commission"
                labelText="Exclude from commission"
                helperText="Tick for products that shouldn't earn sales commission, such as delivery and installation. Applies to sales from when you save; invoices already issued keep their commission."
                checked={form.excludeFromCommission}
                disabled={readOnly || saving}
                onChange={(_, { checked }) => setSettingsDraft((current) => ({ ...current, excludeFromCommission: checked }))}
              />
            </div>
          </Stack>
        </AccordionItem>
      </Accordion>
      {invalidMadeToOrder && (
        <InlineNotification
          kind="error"
          title="Made-to-order offer needs attention"
          subtitle={madeToOrderError}
          hideCloseButton
          lowContrast
        />
      )}
      {!readOnly && (
        <div>
          <Button
            type="button"
            disabled={saving || !hasEdits || invalidPrices || invalidMadeToOrder}
            onClick={() => void handleSave()}
          >
            {saving ? "Saving…" : "Save changes"}
          </Button>
        </div>
      )}
    </Stack>
  );
}

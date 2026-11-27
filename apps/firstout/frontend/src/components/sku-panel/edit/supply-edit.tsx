"use client";

import { Add, Close } from "@carbon/icons-react";
import { Button, Select, SelectItem, TextInput } from "@carbon/react";
import { useQuery } from "@tanstack/react-query";
import { useRef } from "react";
import { canViewCostAudit, getSkuLeadTimes, listSuppliers, updateSku } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import {
  newSupplierRow,
  supplierRowsPayload,
  supplyFormFromSku,
  supplyPayload,
  validateSupply,
  type SupplierRowForm,
  type SupplyForm,
} from "@/lib/catalogue-editor";
import { replaceSkuSupplierPrices, type SkuOverview } from "@/lib/catalogue-lists";
import { formatObservedMedianLine, skuLeadTimeById } from "@/lib/lead-times";
import { CardForm, useCardDraft } from "./shared";
import styles from "../sku-panel.module.css";

type Field = Exclude<keyof SupplyForm, "rows">;

export function SupplyEdit({ overview }: { overview: SkuOverview }) {
  const { sku, supplier_prices: saved } = overview;
  const { user } = useAuth();
  const canViewCost = canViewCostAudit(user);
  const card = useCardDraft(sku.id, () => supplyFormFromSku(sku, saved));
  const { draft, update, errors } = card;
  const nextKey = useRef(0);
  // Same keys as the catalogue page and the read card, so these load once.
  const suppliers = useQuery({ queryKey: ["catalogue", "suppliers"], queryFn: () => listSuppliers() });
  const leadTimes = useQuery({ queryKey: ["catalogue", "lead-times"], queryFn: getSkuLeadTimes });
  const observed = skuLeadTimeById((!leadTimes.error && leadTimes.data?.rows) || []).get(sku.id);
  const active = (suppliers.data ?? []).filter((item) => !item.is_archived);
  // A supplier already on the SKU or a row stays nameable even when archived.
  const supplierName = (id: string) =>
    suppliers.data?.find((item) => item.id === id)?.name ?? saved.find((row) => row.supplier_id === id)?.supplier_name ??
    (id === sku.preferred_supplier_id ? sku.preferred_supplier_name : null) ?? "Unknown supplier";
  const supplierOptions = (current: string) => [
    ...(current && !active.some((item) => item.id === current) ? [{ id: current, name: supplierName(current) }] : []),
    ...active,
  ];

  const field = (name: Field, label: string, helper?: string, type: "text" | "number" | "datetime-local" = "number") => (
    <TextInput
      id={`sku-edit-${name}`}
      labelText={label}
      helperText={helper}
      type={type === "datetime-local" ? type : "text"}
      inputMode={type === "number" ? "numeric" : undefined}
      value={draft[name]}
      invalid={Boolean(errors[name])}
      invalidText={errors[name]}
      disabled={card.saving}
      onChange={(event) => update({ [name]: event.target.value })}
    />
  );
  const setRow = (index: number, patch: Partial<SupplierRowForm>) =>
    update({ rows: draft.rows.map((row, at) => (at === index ? { ...row, ...patch } : row)) },
      Object.keys(patch).map((key) => `rows.${index}.${key}`).concat("rows"));
  const rowInput = (index: number, row: SupplierRowForm, name: keyof SupplierRowForm & string, label: string, numeric = false) => (
    <TextInput
      id={`sku-edit-rows-${index}-${name}`}
      labelText={`Row ${index + 1} ${label}`}
      hideLabel
      size="sm"
      inputMode={numeric ? "numeric" : name.endsWith("price") ? "decimal" : undefined}
      value={String(row[name])}
      invalid={Boolean(errors[`rows.${index}.${name}`])}
      invalidText={errors[`rows.${index}.${name}`]}
      disabled={card.saving}
      onChange={(event) => setRow(index, { [name]: event.target.value })}
    />
  );

  const save = () => void card.save(validateSupply(draft), async () => {
    const payload = supplyPayload(sku, draft);
    const updated = Object.keys(payload).length ? await updateSku(sku.id, payload) : null;
    const rows = supplierRowsPayload(saved, draft.rows, canViewCost);
    if (rows) await replaceSkuSupplierPrices(sku.id, rows);
    return updated;
  });

  return (
    <CardForm id="supply" saving={card.saving} failure={card.failure} onSave={save}>
      <div className={styles.editGrid}>
        <Select
          id="sku-edit-preferred_supplier_id"
          labelText="Preferred supplier"
          value={draft.preferred_supplier_id}
          invalid={Boolean(errors.preferred_supplier_id)}
          invalidText={errors.preferred_supplier_id}
          disabled={card.saving || suppliers.isPending}
          onChange={(event) => update({ preferred_supplier_id: event.target.value })}
        >
          <SelectItem value="" text={suppliers.isPending ? "Loading suppliers…" : "No preferred supplier"} />
          {supplierOptions(draft.preferred_supplier_id).map((item) => <SelectItem key={item.id} value={item.id} text={item.name} />)}
        </Select>
        {field("supplier_ref", "Supplier ref", "The supplier's code, not our barcode.", "text")}
        {field("lead_time_days", "Planned lead time (days)", "Whole days. Leave blank if unknown.")}
        <div>
          <span className={styles.label}>Observed lead time</span>
          <p className={styles.readValue}>{leadTimes.isPending ? "Loading…" : formatObservedMedianLine(observed)}</p>
        </div>
        {field("reorder_min", "Reorder minimum", "Leave blank to keep it off the reorder list.")}
        {field("order_up_to", "Order up to", "A reorder brings stock back to this level.")}
      </div>

      <h4 className={styles.subhead}>Made to order</h4>
      <div className={styles.editGrid}>
        {field("mto_capacity", "Allowance (units)", "Sold beyond stock. A new allowance starts a new allocation.")}
        {field("mto_min_days", "Minimum lead time (days)")}
        {field("mto_max_days", "Maximum lead time (days)")}
        {field("mto_expires_at", "Offer expires", undefined, "datetime-local")}
      </div>
      <p className={styles.help}>Set all four, or clear all four to stop selling beyond stock.</p>

      <h4 className={styles.subhead}>Supplier prices</h4>
      {draft.rows.length === 0 ? <p className={styles.help}>No supplier price rows.</p> : (
        <div className={styles.tableWrap}>
          <table className={`${styles.table} ${styles.editTable}`}>
            <thead>
              <tr>
                <th>Supplier</th><th>Their ref</th>
                {canViewCost && <><th>Latest price</th><th>Fixed price</th></>}
                <th>Minimum order</th><th>Pack multiple</th><th><span className="cds--visually-hidden">Remove</span></th>
              </tr>
            </thead>
            <tbody>
              {draft.rows.map((row, index) => (
                <tr key={row.key}>
                  <td>
                    <Select
                      id={`sku-edit-rows-${index}-supplier_id`}
                      labelText={`Row ${index + 1} supplier`}
                      hideLabel
                      size="sm"
                      value={row.supplier_id}
                      invalid={Boolean(errors[`rows.${index}.supplier_id`])}
                      invalidText={errors[`rows.${index}.supplier_id`]}
                      disabled={card.saving}
                      onChange={(event) => setRow(index, { supplier_id: event.target.value })}
                    >
                      <SelectItem value="" text="Choose a supplier" />
                      {supplierOptions(row.supplier_id).map((item) => <SelectItem key={item.id} value={item.id} text={item.name} />)}
                    </Select>
                  </td>
                  <td>{rowInput(index, row, "supplier_sku", "supplier ref")}</td>
                  {canViewCost && <><td>{rowInput(index, row, "latest_price", "latest price")}</td><td>{rowInput(index, row, "fixed_price", "fixed price")}</td></>}
                  <td>{rowInput(index, row, "min_order_qty", "minimum order", true)}</td>
                  <td>{rowInput(index, row, "pack_multiple", "pack multiple", true)}</td>
                  <td>
                    {(canViewCost || !row.saved) && (
                      <Button kind="ghost" size="sm" hasIconOnly renderIcon={Close} iconDescription={`Remove row ${index + 1}`}
                        tooltipPosition="left" disabled={card.saving}
                        onClick={() => update({ rows: draft.rows.filter((_, at) => at !== index) }, [])} />
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {errors.rows && <p className={styles.fieldError}>{errors.rows}</p>}
      <Button
        kind="ghost"
        size="sm"
        renderIcon={Add}
        disabled={card.saving}
        onClick={() => {
          nextKey.current += 1;
          const used = new Set(draft.rows.map((row) => row.supplier_id));
          const first = [draft.preferred_supplier_id, ...active.map((item) => item.id)].find((id) => id && !used.has(id)) ?? "";
          update({ rows: [...draft.rows, newSupplierRow(`new-${nextKey.current}`, first)] }, []);
        }}
      >
        Add supplier price
      </Button>
      <p className={styles.help}>
        {canViewCost
          ? "Minimum order is the least that supplier accepts; pack multiple is the step it ships in. Reorder suggestions round to both."
          : "Prices are hidden without cost access and stay as they are. You can change refs and quantities, and remove rows you added."}
      </p>
    </CardForm>
  );
}

"use client";

import { TextInput, Toggle } from "@carbon/react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { SkuInvoicePreview } from "@/components/sku-invoice-preview";
import { SkuPriceFields } from "@/components/sku-price-fields";
import { canViewCostAudit, updateSku } from "@/lib/api";
import { formatZarCents } from "@/lib/money";
import { useAuth } from "@/lib/auth";
import { pricingFormFromSku, pricingPayload, validatePricing, withSellMultiple } from "@/lib/catalogue-editor";
import type { SkuOverview } from "@/lib/catalogue-lists";
import { referenceQueries } from "@/lib/queries";
import { buildSkuPriceChanges, validateSkuPriceForm } from "@/lib/sku-price-form";
import { customersSee } from "@/lib/sku-summary";
import { CardForm, useCardDraft } from "./shared";
import styles from "../sku-panel.module.css";

export function PricingEdit({ overview }: { overview: SkuOverview }) {
  const { sku } = overview;
  const { user } = useAuth();
  const canViewCost = canViewCostAudit(user);
  const card = useCardDraft(sku.id, () => pricingFormFromSku(sku));
  const { draft, update, errors } = card;
  // The minimum follows the multiple until it is typed in this edit.
  const [minimumTouched, setMinimumTouched] = useState(false);
  const settings = useQuery(referenceQueries.settings);
  const vatRate = settings.data?.vat_rate;
  const priceErrors = validateSkuPriceForm(draft, vatRate);
  const priceChanges = Object.keys(priceErrors).length ? null : buildSkuPriceChanges(sku, draft);
  const multiple = Number(draft.sell_multiple);
  const minimum = Number(draft.min_sell_qty);
  const cost = sku.average_unit_cost_zar ?? overview.stock.unit_cost_zar;
  const save = () => void card.save(validatePricing(draft, vatRate), () => {
    const payload = pricingPayload(sku, draft);
    return Object.keys(payload).length ? updateSku(sku.id, payload) : Promise.resolve(null);
  });

  return (
    <CardForm id="pricing" saving={card.saving} failure={card.failure} onSave={save}>
      <div className={styles.pricingEdit}>
        <SkuPriceFields
          idPrefix="sku-edit"
          sku={sku}
          form={draft}
          errors={{ ...priceErrors, ...errors }}
          vatRate={vatRate}
          retryVatRate={settings.isLoadingError ? () => void settings.refetch() : undefined}
          canViewCost={canViewCost}
          disabled={card.saving}
          onChange={(field, value) => update({ [field]: value })}
        />
        <SkuInvoicePreview skuId={sku.id} skuRevision={sku.updated_at} active vatRate={vatRate} priceChanges={priceChanges} />
      </div>
      <div className={styles.editGrid}>
        <TextInput
          id="sku-edit-sell_multiple"
          labelText="Sold in multiples of"
          inputMode="numeric"
          value={draft.sell_multiple}
          invalid={Boolean(errors.sell_multiple)}
          invalidText={errors.sell_multiple}
          disabled={card.saving}
          onChange={(event) => update(withSellMultiple(draft, event.target.value, minimumTouched), ["sell_multiple", ...(minimumTouched ? [] : ["min_sell_qty"])])}
        />
        <TextInput
          id="sku-edit-min_sell_qty"
          labelText="Minimum quantity"
          helperText="The smallest quantity one sale line can have."
          inputMode="numeric"
          value={draft.min_sell_qty}
          invalid={Boolean(errors.min_sell_qty)}
          invalidText={errors.min_sell_qty}
          disabled={card.saving}
          onChange={(event) => { setMinimumTouched(true); update({ min_sell_qty: event.target.value }); }}
        />
        <div className={styles.editWide}>
          <span className={styles.label}>Customers see</span>
          <p className={styles.readValue} aria-live="polite">
            {Number.isInteger(multiple) && multiple >= 1 && Number.isInteger(minimum) && minimum >= 1
              ? customersSee(draft.retail_inc_vat.trim() || null, multiple, minimum)
              : "Enter whole numbers to see the line customers read."}
          </p>
        </div>
        <Toggle id="sku-edit-earns_commission" size="sm" labelText="Earns commission" labelA="No" labelB="Yes"
          toggled={draft.earns_commission} disabled={card.saving} onToggle={(value) => update({ earns_commission: value })} />
        {canViewCost && !overview.is_kit && (
          <div>
            <span className={styles.label}>Unit cost</span>
            <p className={styles.readValue}>{formatZarCents(cost)} · from receipts</p>
          </div>
        )}
      </div>
      <p className={styles.help}>Commission changes apply to sales from when you save; issued invoices keep theirs.</p>
    </CardForm>
  );
}

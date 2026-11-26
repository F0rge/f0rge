"use client";

import { Button, InlineLoading, InlineNotification, TextInput } from "@carbon/react";

import type { Sku } from "@/lib/api";
import { formatZarAmount, vatPercentLabel } from "@/lib/money";
import {
  SKU_PRICE_TIERS,
  skuPricePair,
  type SkuPriceErrors,
  type SkuPriceField,
  type SkuPriceForm,
} from "@/lib/sku-price-form";
import styles from "./sku-price-fields.module.css";

type Props = {
  idPrefix: string;
  sku: Sku;
  form: SkuPriceForm;
  errors: SkuPriceErrors;
  vatRate?: string;
  retryVatRate?: () => void;
  canViewCost: boolean;
  readOnly?: boolean;
  disabled?: boolean;
  onChange: (field: SkuPriceField, value: string) => void;
};

export function SkuPriceFields({
  idPrefix,
  sku,
  form,
  errors,
  vatRate,
  retryVatRate,
  canViewCost,
  readOnly,
  disabled,
  onChange,
}: Props) {
  return (
    <fieldset className={styles.fields}>
      <legend>Prices per unit (ZAR){vatRate ? ` · VAT ${vatPercentLabel(vatRate)}` : ""}</legend>
      {!readOnly && vatRate === undefined && (
        <div className={styles.rateState}>
          {retryVatRate ? (
            <>
              <InlineNotification
                kind="error"
                title="Could not load the VAT rate"
                subtitle="Reload the rate to edit prices."
                hideCloseButton
                lowContrast
              />
              <Button kind="ghost" size="sm" onClick={retryVatRate}>Retry VAT rate</Button>
            </>
          ) : <InlineLoading description="Loading VAT rate…" />}
        </div>
      )}
      {SKU_PRICE_TIERS.map((tier) => {
        const retail = tier.field === "retail_inc_vat";
        const value = form[tier.field];
        const error = errors[tier.field];
        const { paired, belowCost } = skuPricePair(sku, tier, value, vatRate, canViewCost);
        return (
          <div className={styles.field} key={tier.field}>
            <TextInput
              id={`${idPrefix}-${tier.field}`}
              labelText={`${tier.label} price (${retail ? "incl." : "excl."} VAT)`}
              inputMode="decimal"
              value={readOnly ? value || "—" : value}
              helperText={
                <>
                  {paired === null
                    ? readOnly ? "No price set." : "Leave blank if unset."
                    : `${formatZarAmount(paired)} ${retail ? "excl." : "incl."} VAT`}
                  {belowCost && <span className={styles.warning}>Price is below average unit cost.</span>}
                </>
              }
              invalid={Boolean(error)}
              invalidText={error}
              readOnly={readOnly || vatRate === undefined}
              disabled={disabled}
              onChange={(event) => onChange(tier.field, event.target.value)}
            />
          </div>
        );
      })}
    </fieldset>
  );
}

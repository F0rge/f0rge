"use client";

import { Button, InlineLoading, Select, SelectItem, Stack, TextInput, Tile } from "@carbon/react";
import { useQuery } from "@tanstack/react-query";
import { useId, useState } from "react";

import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { ApiError, previewSkuPrice, type SkuPricePreviewRequest, type SkuPricePreviewResponse } from "@/lib/api";
import { formatZarAmount, vatPercentLabel } from "@/lib/money";
import { queryKeys } from "@/lib/queries";

import styles from "./sku-invoice-preview.module.css";

const CLASSIFICATIONS = ["Stockist", "Wholesale", "Decorator", "Retail"] as const;
const SOURCE_LABELS: Record<SkuPricePreviewResponse["source"], string> = {
  stockist: "Stockist tier",
  wholesale: "Wholesale tier",
  decorator: "Decorator tier",
  retail: "Retail tier",
  retail_fallback: "Retail fallback",
};

interface SkuInvoicePreviewProps {
  skuId: string;
  skuRevision: string;
  vatRate?: string;
  priceChanges: NonNullable<SkuPricePreviewRequest["price_changes"]> | null;
  active: boolean;
}

export function SkuInvoicePreview({ skuId, skuRevision, vatRate, priceChanges, active }: SkuInvoicePreviewProps) {
  const id = useId();
  const [classification, setClassification] = useState<SkuPricePreviewRequest["classification"]>("Stockist");
  const [quantityInput, setQuantityInput] = useState("1");
  const quantity = Number(quantityInput);
  const validQuantity = /^\d+$/.test(quantityInput) && quantity >= 1 && quantity <= 999;
  const editedPrices = JSON.stringify(priceChanges);
  const settledPrices = useDebouncedValue(editedPrices, 250);
  const settledQuantity = useDebouncedValue(quantity, 250);
  const ready = validQuantity && priceChanges !== null;
  const settled = editedPrices === settledPrices && quantity === settledQuantity;
  const preview = useQuery({
    queryKey: [...queryKeys.skus, skuId, "price-preview", skuRevision, vatRate, classification, settledQuantity, settledPrices],
    queryFn: ({ signal }) => previewSkuPrice(skuId, {
      classification,
      quantity,
      price_changes: priceChanges ?? undefined,
    }, signal),
    enabled: active && ready && settled,
    retry: false,
  });
  const amounts = preview.data;
  const validationMessage = preview.error instanceof ApiError && preview.error.status === 400 &&
    typeof preview.error.detail === "string" ? preview.error.detail : null;

  return (
    <Tile className={styles.preview}>
      <section aria-labelledby={`${id}-heading`}>
        <Stack gap={4}>
          <div>
            <h3 id={`${id}-heading`} className="cds--type-productive-heading-02">Invoice preview</h3>
            <p className={styles.hint}>Uses the selected SKU tier. Assigned customer price lists apply when you create an invoice.</p>
          </div>
          <div className={styles.controls}>
            <Select
              id={`${id}-classification`}
              labelText="Customer tier"
              value={classification}
              onChange={(event) => {
                const selected = CLASSIFICATIONS.find((tier) => tier === event.target.value);
                if (selected) setClassification(selected);
              }}
            >
              {CLASSIFICATIONS.map((tier) => <SelectItem key={tier} value={tier} text={tier} />)}
            </Select>
            <TextInput
              id={`${id}-quantity`}
              labelText="Quantity"
              inputMode="numeric"
              value={quantityInput}
              onChange={(event) => setQuantityInput(event.target.value)}
              invalid={!validQuantity}
              invalidText="Use 1–999."
            />
          </div>
          <div className={styles.result} aria-live="polite">
            {priceChanges === null && <p className={styles.hint}>Correct the price fields to update this preview.</p>}
            {ready && (!settled || preview.isFetching) && <InlineLoading description="Updating invoice preview…" />}
            {ready && settled && !preview.isFetching && preview.isError && (
              validationMessage ? (
                <p className={styles.hint}>{validationMessage.endsWith("has no retail price")
                  ? "Set a price for this tier or Retail to preview this line."
                  : validationMessage}</p>
              ) : (
                <div>
                  <p className={styles.hint}>Could not load the invoice preview.</p>
                  <Button kind="ghost" size="sm" onClick={() => void preview.refetch()}>Try again</Button>
                </div>
              )
            )}
            {ready && settled && !preview.isFetching && preview.isSuccess && amounts && (
              <>
                <dl className={styles.totals}>
                  <div><dt>Unit price excl. VAT</dt><dd>{formatZarAmount(amounts.unit_ex_vat)}</dd></div>
                  <div><dt>Subtotal excl. VAT</dt><dd>{formatZarAmount(amounts.subtotal_ex_vat)}</dd></div>
                  <div><dt>VAT at {vatPercentLabel(amounts.vat_rate)}</dt><dd>{formatZarAmount(amounts.vat_amount)}</dd></div>
                  <div className={styles.total}><dt>Total incl. VAT</dt><dd>{formatZarAmount(amounts.total_inc_vat)}</dd></div>
                </dl>
                <p className={styles.hint}>Price source · {SOURCE_LABELS[amounts.source]}</p>
                {(amounts.source === "retail" || amounts.source === "retail_fallback") && (
                  <p className={styles.hint}>Invoice totals can differ from catalogue prices because invoices round the excl. VAT unit price to cents before adding VAT.</p>
                )}
              </>
            )}
          </div>
        </Stack>
      </section>
    </Tile>
  );
}

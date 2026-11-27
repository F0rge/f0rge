"use client";

import { Tag } from "@carbon/react";
import { canViewCostAudit } from "@/lib/api";
import { formatZarCents } from "@/lib/money";
import { useAuth } from "@/lib/auth";
import { SKU_PRICE_TIERS } from "@/lib/sku-price-form";
import { customersSee, sectionSummary } from "@/lib/sku-summary";
import { Facts, SkuSectionFrame, useSkuSection, type SkuSectionProps } from "./section";
import { PricingEdit } from "../edit/pricing-edit";
import styles from "../sku-panel.module.css";

export function PricingSection({ overview }: SkuSectionProps) {
  const { layout, modeOf } = useSkuSection();
  const { user } = useAuth();
  const { sku } = overview;
  const cost = sku.average_unit_cost_zar ?? overview.stock.unit_cost_zar;
  return (
    <SkuSectionFrame id="pricing" overview={overview} summary={sectionSummary("pricing", overview)}>
      {modeOf("pricing") === "edit" ? <PricingEdit overview={overview} /> : <>
      <dl className={styles.prices}>
        {SKU_PRICE_TIERS.map((tier) => (
          <div key={tier.field}>
            <dt>{tier.label}</dt>
            <dd>{formatZarCents(sku[tier.field])}</dd>
            <small>{tier.field === "retail_inc_vat" ? "incl. VAT" : "excl. VAT"}</small>
            {sku[tier.belowCost] && <Tag size="sm" type="red">Below cost</Tag>}
          </div>
        ))}
      </dl>
      <Facts items={[
        ["Sold in multiples of", String(sku.sell_multiple)],
        ["Minimum quantity", String(sku.min_sell_qty)],
        ["Customers see", customersSee(sku.retail_inc_vat, sku.sell_multiple, sku.min_sell_qty), true],
        ["Earns commission", sku.exclude_from_commission ? "No" : "Yes"],
        layout === "full" && canViewCostAudit(user) && !overview.is_kit && ["Unit cost", formatZarCents(cost)],
      ]} />
      </>}
    </SkuSectionFrame>
  );
}

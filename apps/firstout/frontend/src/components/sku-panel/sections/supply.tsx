"use client";

import { Tag } from "@carbon/react";
import { useQuery } from "@tanstack/react-query";
import { getSkuLeadTimes } from "@/lib/api";
import { formatObservedMedianLine, skuLeadTimeById } from "@/lib/lead-times";
import { formatZarCents } from "@/lib/money";
import { formatCount, sectionSummary } from "@/lib/sku-summary";
import { Facts, SkuSectionFrame, useSkuSection, type SkuSectionProps } from "./section";
import { SupplyEdit } from "../edit/supply-edit";
import styles from "../sku-panel.module.css";

type PriceRow = SkuSectionProps["overview"]["supplier_prices"][number];

const days = (value: number | null) => (value === null ? null : `${value} days`);
const qty = (value: number | null) => (value === null ? "—" : formatCount(value));
/** Prices are null without stock.cost.view; the fixed price wins over the latest one when set. */
const price = (row: PriceRow) => row.fixed_price ?? row.latest_price;
const money = (row: PriceRow) => formatZarCents(price(row));

function madeToOrder(sku: SkuSectionProps["overview"]["sku"]): string | null {
  if (sku.made_to_order_capacity === null) return null;
  const min = sku.made_to_order_lead_time_min_days;
  const max = sku.made_to_order_lead_time_max_days;
  const lead = min !== null && max !== null ? (min === max ? `${min} days` : `${min} to ${max} days`) : null;
  return [`${sku.made_to_order_capacity} beyond stock`, lead].filter(Boolean).join(" · ");
}

export function SupplySection({ overview }: SkuSectionProps) {
  const { layout, modeOf } = useSkuSection();
  const { sku, supplier_prices: rows } = overview;
  // Same key as the catalogue page, so the report loads once.
  const leadTimes = useQuery({ queryKey: ["catalogue", "lead-times"], queryFn: getSkuLeadTimes, enabled: !overview.is_kit });
  const observed = skuLeadTimeById((!leadTimes.error && leadTimes.data?.rows) || []).get(sku.id);
  const showPrices = rows.some((row) => price(row) !== null);
  return (
    <SkuSectionFrame id="supply" overview={overview} summary={sectionSummary("supply", overview)}>
      {modeOf("supply") === "edit" ? <SupplyEdit overview={overview} /> : overview.is_kit ? (
        <p className={styles.help}>Not bought in. Reorders happen on its parts.</p>
      ) : (
        <>
          <Facts items={[
            ["Preferred supplier", sku.preferred_supplier_name],
            ["Supplier ref", sku.supplier_ref ? <code>{sku.supplier_ref}</code> : null],
            ["Planned lead time", days(sku.lead_time_days)],
            ["Observed lead time", leadTimes.isPending ? "Loading…" : observed ? formatObservedMedianLine(observed) : null],
            ["Reorder minimum", sku.do_not_reorder ? "Do not reorder" : sku.reorder_min === null ? null : formatCount(sku.reorder_min)],
            ["Order up to", sku.order_up_to === null ? null : formatCount(sku.order_up_to)],
            ["Made to order", madeToOrder(sku)],
          ]} />
          <h4 className={styles.subhead}>Supplier prices</h4>
          {rows.length === 0 ? (
            <p className={styles.help}>No supplier price rows.</p>
          ) : layout === "full" ? (
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Supplier</th><th>Their ref</th>{showPrices && <th className={styles.num}>Price</th>}
                    <th className={styles.num}>Minimum order</th><th className={styles.num}>Pack multiple</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id}>
                      <td>{row.supplier_name} {row.is_preferred && <Tag size="sm" type="blue">Preferred</Tag>}{row.supplier_is_archived && <Tag size="sm" type="gray">Archived</Tag>}</td>
                      <td><code>{row.supplier_sku ?? "—"}</code></td>
                      {showPrices && <td className={styles.num}>{money(row)}</td>}
                      <td className={styles.num}>{qty(row.min_order_qty)}</td>
                      <td className={styles.num}>{qty(row.pack_multiple)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <ul className={styles.lines}>
              {rows.map((row) => (
                <li key={row.id}>
                  <span>
                    {row.supplier_name}{row.is_preferred && " (preferred)"}
                    <small>
                      {[row.supplier_sku, row.min_order_qty !== null && `minimum ${formatCount(row.min_order_qty)}`, row.pack_multiple !== null && `packs of ${formatCount(row.pack_multiple)}`]
                        .filter(Boolean).join(" · ") || "No ordering rules"}
                    </small>
                  </span>
                  {showPrices && <span>{money(row)}</span>}
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </SkuSectionFrame>
  );
}

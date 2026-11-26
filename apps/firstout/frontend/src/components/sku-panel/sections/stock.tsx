"use client";

import Link from "next/link";
import { canViewCostAudit, formatZarAmount } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatCount, nextArrivalText, sectionSummary } from "@/lib/sku-summary";
import { SkuSectionFrame, useSkuSection, type SkuSectionProps } from "./section";
import styles from "../sku-panel.module.css";

type Location = SkuSectionProps["overview"]["stock"]["locations"][number];

const bins = (location: Location) =>
  location.bins.length ? location.bins.map((bin) => `${bin.code}: ${formatCount(bin.on_hand)}`).join(", ") : "No bins";

export function StockSection({ overview }: SkuSectionProps) {
  const { layout } = useSkuSection();
  const { user } = useAuth();
  const { stock } = overview;
  const full = layout === "full";
  const showCost = canViewCostAudit(user);
  const arrival = stock.next_arrival;
  return (
    <SkuSectionFrame id="stock" overview={overview} summary={sectionSummary("stock", overview)} note="All locations">
      {overview.is_kit ? (
        <>
          <dl className={styles.figures}>
            <div><dt>Available</dt><dd>{formatCount(stock.available)}</dd></div>
          </dl>
          <p className={styles.help}>A kit holds no stock of its own. Available follows its parts.</p>
        </>
      ) : (
        <>
          <dl className={styles.figures}>
            <div><dt>On hand</dt><dd>{formatCount(stock.on_hand)}</dd></div>
            <div>
              <dt>Held</dt><dd>{formatCount(stock.held)}</dd>
              {stock.held_documents.length > 0 && (
                <small>{stock.held_documents.map((doc) => `${doc.number}${doc.kind === "layby" ? " (lay-by)" : ""}`).join(", ")}</small>
              )}
            </div>
            <div><dt>Available</dt><dd>{formatCount(stock.available)}</dd></div>
            <div><dt>On order</dt><dd>{formatCount(stock.on_order)}</dd></div>
          </dl>
          {stock.locations.length === 0 ? (
            <p className={styles.help}>No stock at any location.</p>
          ) : full ? (
            <div className={styles.tableWrap}>
              <table className={styles.table}>
                <thead><tr><th>Location</th><th>Bins</th><th className={styles.num}>On hand</th>{showCost && <th className={styles.num}>Unit cost</th>}</tr></thead>
                <tbody>
                  {stock.locations.map((location) => (
                    <tr key={location.location_id}>
                      <td>{location.location_name}</td>
                      <td>{bins(location)}</td>
                      <td className={styles.num}>{formatCount(location.on_hand)}</td>
                      {showCost && <td className={styles.num}>{formatZarAmount(location.unit_cost_zar)}</td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <ul className={styles.lines}>
              {stock.locations.map((location) => (
                <li key={location.location_id}>
                  <span>{location.location_name}<small>{bins(location)}</small></span>
                  <span>{formatCount(location.on_hand)}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
      <p className={styles.arrival}>
        <span className={styles.label}>Next arrival</span>
        {arrival ? <Link href={`/purchase-orders/${arrival.purchase_order_id}`}>{nextArrivalText(arrival)}</Link> : nextArrivalText(arrival)}
        {arrival?.expected_on_basis === "planned_lead_time" && <small>Estimated from the planned lead time</small>}
      </p>
      {full && <p className={styles.help}>Stock changes through receiving, transfers and adjustments.</p>}
    </SkuSectionFrame>
  );
}

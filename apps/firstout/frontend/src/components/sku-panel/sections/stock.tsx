"use client";

import { Button, TextInput } from "@carbon/react";
import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { canViewCostAudit, correctUnitCost } from "@/lib/api";
import { canManageUsers, canReceive } from "@/lib/permissions";
import { formatZarCents } from "@/lib/money";
import { useAuth } from "@/lib/auth";
import { adjustStockHref } from "@/lib/sku-panel";
import { formatCount, nextArrivalText, sectionSummary } from "@/lib/sku-summary";
import { refreshSku } from "../edit/shared";
import { useSkuPanel } from "../provider";
import { SkuSectionFrame, useSkuSection, type SkuSectionProps } from "./section";
import styles from "../sku-panel.module.css";

type Location = SkuSectionProps["overview"]["stock"]["locations"][number];

const bins = (location: Location) =>
  location.bins.length ? location.bins.map((bin) => `${bin.code}: ${formatCount(bin.on_hand)}`).join(", ") : "No bins";

/** Owner-only correction of one location's weighted unit cost; it is recorded in the cost history. */
function CostCorrection({ skuId, location, onDone }: { skuId: string; location: Location; onDone: () => void }) {
  const client = useQueryClient();
  const [value, setValue] = useState(location.unit_cost_zar ? Number(location.unit_cost_zar).toFixed(2) : "");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  async function save() {
    if (!/^\d+(?:\.\d{1,4})?$/.test(value.trim()) || Number(value) <= 0) {
      setError("Enter a unit cost above 0, up to 4 decimals.");
      return;
    }
    setSaving(true);
    try {
      await correctUnitCost(skuId, { location_id: location.location_id, unit_cost_zar: value.trim() });
      await refreshSku(client, skuId);
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not correct the cost.");
      setSaving(false);
    }
  }
  return (
    <form className={styles.correction} onSubmit={(event) => { event.preventDefault(); void save(); }}>
      <TextInput id={`cost-${location.location_id}`} size="sm" labelText={`New unit cost at ${location.location_name} (excl. VAT)`}
        inputMode="decimal" value={value} invalid={Boolean(error)} invalidText={error ?? undefined} disabled={saving}
        onChange={(event) => { setValue(event.target.value); setError(null); }} />
      <Button kind="primary" size="sm" type="submit" disabled={saving}>{saving ? "Saving…" : "Save cost"}</Button>
      <Button kind="ghost" size="sm" disabled={saving} onClick={onDone}>Cancel</Button>
    </form>
  );
}

export function StockSection({ overview }: SkuSectionProps) {
  const { layout } = useSkuSection();
  const { user } = useAuth();
  const { stock } = overview;
  const full = layout === "full";
  const showCost = canViewCostAudit(user);
  const canCorrect = showCost && canManageUsers(user);
  const [correcting, setCorrecting] = useState<string | null>(null);
  const panel = useSkuPanel();
  const arrival = stock.next_arrival;
  const adjustHref = adjustStockHref(overview.sku.id);
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
                <thead>
                  <tr>
                    <th>Location</th><th>Bins</th><th className={styles.num}>On hand</th>
                    {showCost && <th className={styles.num}>Unit cost</th>}
                    {canCorrect && <th><span className="cds--visually-hidden">Correct cost</span></th>}
                  </tr>
                </thead>
                <tbody>
                  {stock.locations.map((location) => (
                    <tr key={location.location_id}>
                      <td>{location.location_name}</td>
                      <td>{bins(location)}</td>
                      <td className={styles.num}>{formatCount(location.on_hand)}</td>
                      {showCost && <td className={styles.num}>{formatZarCents(location.unit_cost_zar)}</td>}
                      {canCorrect && (
                        <td className={styles.num}>
                          <Button kind="ghost" size="sm" onClick={() => setCorrecting(location.location_id)}>Correct cost</Button>
                        </td>
                      )}
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
      {full && correcting && stock.locations.some((item) => item.location_id === correcting) && (
        <CostCorrection
          key={correcting}
          skuId={overview.sku.id}
          location={stock.locations.find((item) => item.location_id === correcting) as Location}
          onDone={() => setCorrecting(null)}
        />
      )}
      {full && (
        <p className={styles.help}>
          Stock changes through receiving, transfers and adjustments.
          {canReceive(user) && !overview.is_kit && (
            <> <Link href={adjustHref} onClick={(event) => {
              if (event.button !== 0 || event.metaKey || event.ctrlKey || !panel) return;
              event.preventDefault();
              panel.navigate(adjustHref);
            }}>Adjust stock</Link></>
          )}
        </p>
      )}
    </SkuSectionFrame>
  );
}

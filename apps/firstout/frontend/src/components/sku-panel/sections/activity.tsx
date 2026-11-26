"use client";

import { formatZarAmount } from "@/lib/api";
import { formatDay, sectionSummary } from "@/lib/sku-summary";
import { SkuSectionFrame, useSkuSection, type SkuSectionProps } from "./section";
import styles from "../sku-panel.module.css";

const PANEL_ROWS = 3;

export function ActivitySection({ overview }: SkuSectionProps) {
  const { layout } = useSkuSection();
  const rows = layout === "full" ? overview.activity : overview.activity.slice(0, PANEL_ROWS);
  const more = overview.activity.length - rows.length;
  return (
    <SkuSectionFrame id="activity" overview={overview} summary={sectionSummary("activity", overview)} note="Recorded automatically">
      {rows.length === 0 ? <p className={styles.help}>No cost or stock events recorded yet.</p> : (
        <ul className={styles.lines}>
          {rows.map((row) => (
            <li key={row.id}>
              <span>
                {row.source_label}
                <small>
                  {[
                    row.location_name,
                    row.old_cost_zar !== null || row.new_cost_zar !== null ? `${formatZarAmount(row.old_cost_zar)} to ${formatZarAmount(row.new_cost_zar)}` : null,
                    row.note,
                  ].filter(Boolean).join(" · ")}
                </small>
              </span>
              <span className={styles.help}>{formatDay(row.created_at)}</span>
            </li>
          ))}
        </ul>
      )}
      {more > 0 && <p className={styles.help}>{more} more in the full view</p>}
    </SkuSectionFrame>
  );
}

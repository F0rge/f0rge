"use client";

import { CostAuditPanel } from "@/components/cost-audit-panel";
import { canViewCostAudit } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatZarCents } from "@/lib/money";
import { formatDay, sectionSummary } from "@/lib/sku-summary";
import { SkuSectionFrame, useSkuSection, type SkuSectionProps } from "./section";
import styles from "../sku-panel.module.css";

const PANEL_ROWS = 3;

export function ActivitySection({ overview }: SkuSectionProps) {
  const { layout } = useSkuSection();
  const { user } = useAuth();
  // Cost viewers get the full cost history (who changed it, old and new cost) in the full view.
  const costHistory = layout === "full" && canViewCostAudit(user);
  const rows = layout === "full" ? overview.activity : overview.activity.slice(0, PANEL_ROWS);
  const more = overview.activity.length - rows.length;
  return (
    <SkuSectionFrame id="activity" overview={overview} summary={sectionSummary("activity", overview)} note="Recorded automatically">
      {costHistory ? (
        <>
          {overview.sku.last_landed_cost_zar && <p className={styles.help}>Last landed cost {formatZarCents(overview.sku.last_landed_cost_zar)}</p>}
          <CostAuditPanel pinnedSkuId={overview.sku.id} />
        </>
      ) : rows.length === 0 ? <p className={styles.help}>No cost or stock events recorded yet.</p> : (
        <ul className={styles.lines}>
          {rows.map((row) => (
            <li key={row.id}>
              <span>
                {row.source_label}
                <small>
                  {[
                    row.location_name,
                    row.old_cost_zar !== null || row.new_cost_zar !== null ? `${formatZarCents(row.old_cost_zar)} to ${formatZarCents(row.new_cost_zar)}` : null,
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

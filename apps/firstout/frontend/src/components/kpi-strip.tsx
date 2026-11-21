import { SkeletonText } from "@carbon/react";

import styles from "./kpi-strip.module.css";

export type Kpi = { label: string; value: string; sub?: string; warn?: boolean };

/** A row of summary tiles; `items` undefined renders the loading state, null a failed load. */
export function KpiStrip({ label, items, count }: { label: string; items?: readonly Kpi[] | null; count: number }) {
  if (items === null) {
    return (
      <dl aria-label={label} className={styles.kpis}>
        <div className={styles.kpi}>
          <dt>{label}</dt>
          <dd>—</dd>
          <dd className={styles.sub}>Could not be loaded</dd>
        </div>
      </dl>
    );
  }
  return (
    <dl aria-label={label} aria-busy={!items} className={styles.kpis}>
      {(items ?? Array.from({ length: count }, () => null)).map((item, index) => (
        <div key={item?.label ?? index} className={`${styles.kpi}${item?.warn ? ` ${styles.warn}` : ""}`}>
          {item ? (
            <>
              <dt>{item.label}</dt>
              <dd>{item.value}</dd>
              {item.sub ? <dd className={styles.sub}>{item.sub}</dd> : null}
            </>
          ) : (
            <>
              <dt><SkeletonText width="6rem" /></dt>
              <dd><SkeletonText heading width="5rem" /></dd>
            </>
          )}
        </div>
      ))}
    </dl>
  );
}

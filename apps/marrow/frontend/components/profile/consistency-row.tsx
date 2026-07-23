'use client'

import { useEntryStats } from '@/lib/api/hooks'

/** "This week" text summary: X of 7 days checked in. */
export function ConsistencyRow() {
  const stats = useEntryStats().data
  // Guard the whole payload: narrowing week_days alone leaves `stats` optional.
  if (stats == null) return null

  const done = stats.week_days.filter(Boolean).length

  return (
    <section>
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
          This week
        </h2>
        <p className="text-[12px] text-muted-foreground">
          <b className="font-bold tabular-nums text-foreground">{done} of 7</b> days checked in
        </p>
      </div>
    </section>
  )
}

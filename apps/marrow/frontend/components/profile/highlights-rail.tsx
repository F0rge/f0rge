'use client'

import { Activity, Heart, Moon, Wind, Zap, type LucideIcon } from 'lucide-react'
import { useInsightsTrends } from '@/lib/api/hooks'

// Fixed subset of the trends series keys (services/insights.py) worth a
// glanceable circle; labels come from the series payload itself.
const HIGHLIGHT_KEYS: { key: string; icon: LucideIcon }[] = [
  { key: 'overall', icon: Activity },
  { key: 'sleep_quality', icon: Moon },
  { key: 'stress', icon: Zap },
  { key: 'bloating', icon: Wind },
  { key: 'hm_resting_hr', icon: Heart },
]

function isoDaysAgo(days: number): string {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return d.toISOString().slice(0, 10)
}

export function HighlightsRail() {
  const trends = useInsightsTrends(isoDaysAgo(6), isoDaysAgo(0))
  const series = trends.data?.series ?? []

  const items = HIGHLIGHT_KEYS.flatMap(({ key, icon }) => {
    const match = series.find((s) => s.key === key)
    const value = match?.rolling_avg_7 ?? match?.current
    if (match == null || value == null) return []
    return [{ key, icon, label: match.label, value: Math.round(value * 10) / 10 }]
  })

  if (items.length === 0) return null

  return (
    <div className="flex gap-4 overflow-x-auto pb-1" aria-label="This week at a glance">
      {items.map(({ key, icon: Icon, label, value }) => (
        <div key={key} className="w-[60px] flex-none text-center">
          <div className="mx-auto mb-1 flex size-14 flex-col items-center justify-center gap-0.5 rounded-full border border-border bg-muted">
            <Icon className="size-4 text-muted-foreground" aria-hidden />
            <span className="text-[11px] font-bold tabular-nums">{value}</span>
          </div>
          <span className="block truncate text-[11px] text-muted-foreground">{label}</span>
        </div>
      ))}
    </div>
  )
}

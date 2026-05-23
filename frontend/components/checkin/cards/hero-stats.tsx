'use client'

import { cn } from '@/lib/utils'
import type { HeroStatsData } from '@/lib/checkin/hero-stats'

interface HeroStatsTileProps {
  label: string
  value: string
  subline?: string | null
  valueClass?: string
  tintClass: string
  hideOnMobile?: boolean
}

function HeroStatsTile({
  label,
  value,
  subline,
  valueClass,
  tintClass,
  hideOnMobile,
}: HeroStatsTileProps) {
  return (
    <div
      className={cn(
        'px-4 py-3.5',
        tintClass,
        hideOnMobile && 'hidden lg:block',
      )}
    >
      <div className="text-[10px] text-muted-foreground uppercase tracking-wider">{label}</div>
      <div className={cn('text-base font-bold mt-0.5 leading-tight', valueClass)}>{value}</div>
      {subline && <div className="text-[10px] text-muted-foreground mt-0.5">{subline}</div>}
    </div>
  )
}

const HISTAMINE_COLOR: Record<string, string> = {
  emerald: 'text-emerald-700 dark:text-emerald-400',
  amber: 'text-amber-700 dark:text-amber-400',
  orange: 'text-orange-700 dark:text-orange-400',
}

interface HeroStatsProps {
  data: HeroStatsData
}

export function HeroStats({ data }: HeroStatsProps) {
  const { overall, sleep, gut, histamine, treatment } = data
  const cols = treatment ? 'grid-cols-3 lg:grid-cols-5' : 'grid-cols-3 lg:grid-cols-4'

  // Gut tint mirrors KPI state: emerald (good), rose (severe), amber (mid).
  const gutTint =
    gut.label === 'None'
      ? 'bg-emerald-50 dark:bg-emerald-950/40'
      : gut.label.includes('Severe')
        ? 'bg-rose-50 dark:bg-rose-950/40'
        : 'bg-amber-50 dark:bg-amber-950/40'

  return (
    <div
      className={cn(
        'grid divide-x divide-border rounded-xl border border-border overflow-hidden',
        cols,
      )}
    >
      <HeroStatsTile
        label="Overall"
        value={overall.label}
        subline={overall.trendLabel}
        tintClass="bg-indigo-50 dark:bg-indigo-950/40"
      />
      <HeroStatsTile
        label="Sleep"
        value={sleep.label}
        subline={sleep.trendLabel}
        tintClass="bg-sky-50 dark:bg-sky-950/40"
        valueClass={
          sleep.label === 'Good'
            ? 'text-sky-700 dark:text-sky-300'
            : sleep.label === 'Poor'
              ? 'text-red-700 dark:text-red-400'
              : undefined
        }
      />
      <HeroStatsTile
        label="Gut"
        value={gut.label}
        subline={gut.trendLabel}
        tintClass={gutTint}
        valueClass={
          gut.label === 'None'
            ? 'text-emerald-700 dark:text-emerald-400'
            : gut.label.includes('Severe')
              ? 'text-rose-700 dark:text-rose-300'
              : 'text-amber-700 dark:text-amber-400'
        }
        hideOnMobile
      />
      <HeroStatsTile
        label="Histamine"
        value={histamine.load !== null ? `Load ${histamine.load}` : '—'}
        subline={
          histamine.load !== null
            ? histamine.highDaysInWindow > 0
              ? `high · day ${histamine.highDaysInWindow}`
              : 'low window'
            : 'no photos'
        }
        tintClass="bg-amber-50 dark:bg-amber-950/40"
        valueClass={histamine.load !== null ? HISTAMINE_COLOR[histamine.colorBand] : undefined}
      />
      {treatment && (
        <HeroStatsTile
          label="Treatment"
          value={treatment.name.length > 22 ? treatment.name.slice(0, 21) + '…' : treatment.name}
          subline={
            treatment.totalDays
              ? `day ${treatment.dayNum} of ${treatment.totalDays}${treatment.extraCount > 0 ? ` +${treatment.extraCount}` : ''}`
              : `day ${treatment.dayNum}${treatment.extraCount > 0 ? ` +${treatment.extraCount}` : ''}`
          }
          tintClass="bg-violet-50 dark:bg-violet-950/40"
        />
      )}
    </div>
  )
}

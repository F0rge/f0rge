'use client'

import { cn } from '@/lib/utils'
import type { HeroStatsData } from '@/lib/checkin/hero-stats'

interface HeroStatsTileProps {
  label: string
  value: string
  subline?: string | null
  valueClass?: string
}

function HeroStatsTile({ label, value, subline, valueClass }: HeroStatsTileProps) {
  return (
    <div>
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

  return (
    <div className={cn(
      'grid gap-4 p-4 rounded-xl',
      'bg-gradient-to-r from-indigo-50 to-amber-50 dark:from-indigo-950/40 dark:to-amber-950/40',
      'border border-border',
      cols,
    )}>
      <HeroStatsTile
        label="Overall"
        value={overall.label}
        subline={overall.trendLabel}
      />
      <HeroStatsTile
        label="Sleep"
        value={sleep.label}
        subline={sleep.trendLabel}
        valueClass={
          sleep.label === 'Good' ? 'text-emerald-700 dark:text-emerald-400' :
          sleep.label === 'Poor' ? 'text-red-600 dark:text-red-400' : undefined
        }
      />
      {/* Gut — hidden on mobile, shown on desktop in 4th/5th positions */}
      <div className="hidden lg:block">
        <HeroStatsTile
          label="Gut"
          value={gut.label}
          subline={gut.trendLabel}
          valueClass={
            gut.label === 'None' ? 'text-emerald-700 dark:text-emerald-400' :
            gut.label.includes('Severe') ? 'text-red-600 dark:text-red-400' :
            'text-amber-700 dark:text-amber-400'
          }
        />
      </div>

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
        />
      )}
    </div>
  )
}

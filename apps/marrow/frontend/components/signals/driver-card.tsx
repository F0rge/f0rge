'use client'

import { useState } from 'react'
import { Badge, cn } from '@f0rge/ui'
import type { SignalsDriver } from '@/lib/api/types/signals'
import { crossesZero, polarityTone } from './polarity'
import { DriverDetail } from './driver-detail'

interface Props {
  driver: SignalsDriver
}

function tierVariant(tier: string): 'default' | 'secondary' | 'outline' {
  if (tier === 'strong') return 'default'
  if (tier === 'moderate') return 'secondary'
  return 'outline'
}

export function DriverCard({ driver }: Props) {
  const [open, setOpen] = useState(false)
  const effect = driver.theta_hat
  const crosses = crossesZero(driver.ci_low, driver.ci_high)

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={cn(
          'w-full rounded-xl bg-card p-3 text-left ring-1 ring-foreground/10',
          'transition-colors hover:bg-muted/40 active:bg-muted/60',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        )}
      >
        <div className="mb-2 flex flex-wrap items-center gap-1.5">
          <span className="truncate text-sm font-medium">{driver.label}</span>
          <Badge variant={tierVariant(driver.tier)} className="text-[10px]">
            {driver.tier}
          </Badge>
          <Badge variant="outline" className="text-[10px] capitalize">
            {driver.feature_class}
          </Badge>
          {crosses && (
            <Badge variant="outline" className="text-[10px]">
              crosses zero
            </Badge>
          )}
        </div>
        <div className="flex items-baseline justify-between gap-2">
          <span
            className={cn(
              'text-lg font-semibold tabular-nums',
              effect != null ? polarityTone(effect, driver.good_direction) : 'text-muted-foreground',
            )}
          >
            {effect != null ? (effect >= 0 ? `+${effect.toFixed(2)}` : effect.toFixed(2)) : '—'}
          </span>
          <span className="text-xs text-muted-foreground tabular-nums">
            {driver.ci_low != null && driver.ci_high != null
              ? `[${driver.ci_low.toFixed(2)}, ${driver.ci_high.toFixed(2)}]`
              : '—'}
          </span>
        </div>
        <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{driver.reason}</p>
      </button>

      <DriverDetail driver={driver} open={open} onOpenChange={setOpen} />
    </>
  )
}

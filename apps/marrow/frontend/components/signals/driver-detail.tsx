'use client'

import { useEffect } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  Badge,
  cn,
} from '@f0rge/ui'
import type { SignalsDriver } from '@/lib/api/types/signals'
import { crossesZero, polarityTone } from './polarity'
import { DayStrip } from './day-strip'
import { DoseTable } from './dose-table'

interface Props {
  driver: SignalsDriver
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function DriverDetail({ driver, open, onOpenChange }: Props) {
  useEffect(() => {
    if (!open) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onOpenChange(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onOpenChange])

  const effect = driver.theta_hat
  const crosses = crossesZero(driver.ci_low, driver.ci_high)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-sm overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{driver.label}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 text-sm">
          <div className="flex flex-wrap gap-1.5">
            <Badge variant="outline" className="capitalize">
              {driver.feature_class}
            </Badge>
            <Badge>{driver.tier}</Badge>
            {crosses && <Badge variant="outline">uncertain</Badge>}
          </div>

          <div>
            <p className="text-xs text-muted-foreground">Effect</p>
            <p
              className={cn(
                'text-xl font-semibold tabular-nums',
                effect != null
                  ? polarityTone(effect, driver.good_direction)
                  : 'text-muted-foreground',
              )}
            >
              {effect != null
                ? effect >= 0
                  ? `+${effect.toFixed(3)}`
                  : effect.toFixed(3)
                : '—'}
            </p>
            {driver.ci_low != null && driver.ci_high != null && (
              <p className="text-xs text-muted-foreground tabular-nums">
                Range [{driver.ci_low.toFixed(3)}, {driver.ci_high.toFixed(3)}]
              </p>
            )}
          </div>

          <p className="text-xs text-muted-foreground">{driver.reason}</p>

          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Day strips
            </h3>
            <DayStrip
              strips={driver.day_strips}
              exposedDays={driver.exposed_days}
              unexposedDays={driver.unexposed_days}
            />
          </div>

          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Dose response
            </h3>
            <DoseTable rows={driver.dose_table} />
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

'use client'

import { cn } from '@f0rge/ui'
import type { DayStrips as DayStripsData } from '@/lib/api/types/signals'
import { statusFill } from '@/lib/ui/status'

interface Props {
  strips: DayStripsData
  exposedDays: number
  unexposedDays: number
}

function stripColor(value: number | null): string {
  if (value === null) return 'bg-muted'
  if (value >= 0.66) return `${statusFill.ok}/80`
  if (value >= 0.33) return `${statusFill.warn}/80`
  return `${statusFill.destructive}/80`
}

function StripRow({
  label,
  values,
  count,
}: {
  label: string
  values: (number | null)[]
  count: number
}) {
  return (
    <div>
      <p className="mb-1 text-xs text-muted-foreground">
        {label} ({count})
      </p>
      <div className="flex flex-wrap gap-0.5" aria-hidden>
        {values.map((v, i) => (
          <div
            key={`${label}-${i}`}
            className={cn('size-2.5 rounded-sm', stripColor(v))}
          />
        ))}
      </div>
    </div>
  )
}

export function DayStrip({ strips, exposedDays, unexposedDays }: Props) {
  return (
    <div className="space-y-2">
      <StripRow label="Exposed" values={strips.exposed} count={exposedDays} />
      <StripRow label="Unexposed" values={strips.unexposed} count={unexposedDays} />
    </div>
  )
}

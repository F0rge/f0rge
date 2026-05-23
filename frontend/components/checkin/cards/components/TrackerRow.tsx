'use client'

import { Archive, Circle, Coffee, Droplets, Thermometer, Wine } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { Stepper } from '@/components/ui/stepper'
import { BinaryInput } from '@/components/checkin/binary-input'
import type { Tracker } from '@/lib/api/types'

// Map the 4 known seeded icon names to lucide components.
// Falls back to Circle for unknown lucide names; renders string directly for emoji.
const ICON_MAP: Record<string, LucideIcon> = {
  wine: Wine,
  coffee: Coffee,
  thermometer: Thermometer,
  droplets: Droplets,
}

interface TrackerRowProps {
  tracker: Tracker
  value: number
  onChange: (v: number) => void
  onArchive?: () => void
}

function TrackerIcon({ icon }: { icon: string | null }) {
  if (!icon) return <Circle className="size-4 text-muted-foreground shrink-0" />

  const LucideComp = ICON_MAP[icon.toLowerCase()]
  if (LucideComp) {
    return <LucideComp className="size-4 text-muted-foreground shrink-0" />
  }

  // Treat as emoji / freeform text
  return (
    <span className="text-base leading-none shrink-0" aria-hidden="true">
      {icon}
    </span>
  )
}

export function TrackerRow({ tracker, value, onChange, onArchive }: TrackerRowProps) {
  if (tracker.kind === 'binary') {
    return (
      <div className="group flex items-start gap-2">
        <div className="mt-1 shrink-0">
          <TrackerIcon icon={tracker.icon} />
        </div>
        <div className="flex-1 min-w-0">
          <BinaryInput
            label={tracker.name}
            value={value === 1}
            onChange={(v) => onChange(v ? 1 : 0)}
            trueLabel="Yes"
            falseLabel="No"
          />
        </div>
        {!tracker.is_seed && onArchive && (
          <button
            type="button"
            onClick={onArchive}
            aria-label={`Archive ${tracker.name}`}
            className="mt-1 shrink-0 rounded p-1 opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100 hover:text-destructive"
          >
            <Archive className="size-4" />
          </button>
        )}
      </div>
    )
  }

  // counter — Stepper carries the label and tooltip (unit); icon is visual only
  const unitTooltip = tracker.unit ? `per ${tracker.unit}` : undefined
  return (
    <div className="group flex items-center gap-3">
      <TrackerIcon icon={tracker.icon} />
      <div className="flex flex-1 items-center justify-center">
        <Stepper
          value={value}
          onChange={onChange}
          min={0}
          max={99}
          label={tracker.name}
          tooltip={unitTooltip}
        />
      </div>
      {!tracker.is_seed && onArchive && (
        <button
          type="button"
          onClick={onArchive}
          aria-label={`Archive ${tracker.name}`}
          className="shrink-0 rounded p-1 opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100 hover:text-destructive"
        >
          <Archive className="size-4" />
        </button>
      )}
    </div>
  )
}

'use client'

import { useState } from 'react'
import { cn } from '@f0rge/ui'

interface MealTimeChipsProps {
  value: Date | null
  onChange: (d: Date) => void
  /** Calendar day to anchor preset/custom times on (defaults to today). */
  referenceDate?: Date
}

type Preset = { label: string; offsetHours: number } | { label: 'Custom' }

const PRESETS: Preset[] = [
  { label: 'Now', offsetHours: 0 },
  { label: '1h ago', offsetHours: 1 },
  { label: '2h ago', offsetHours: 2 },
  { label: '3h ago', offsetHours: 3 },
  { label: 'Custom' },
]

function formatHHMM(d: Date): string {
  return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false })
}

function toTimeInputValue(d: Date): string {
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${hh}:${mm}`
}

function applyTimeOntoDay(day: Date, source: Date): Date {
  const d = new Date(day)
  d.setHours(source.getHours(), source.getMinutes(), source.getSeconds(), source.getMilliseconds())
  return d
}

export function MealTimeChips({ value, onChange, referenceDate }: MealTimeChipsProps) {
  const [showCustom, setShowCustom] = useState(false)
  const dayAnchor = referenceDate ?? new Date()

  const handlePreset = (preset: Preset) => {
    if ('label' in preset && preset.label === 'Custom') {
      setShowCustom(true)
      return
    }
    const p = preset as { label: string; offsetHours: number }
    setShowCustom(false)
    const now = new Date()
    now.setMinutes(now.getMinutes() - p.offsetHours * 60)
    const d = referenceDate ? applyTimeOntoDay(referenceDate, now) : now
    onChange(d)
  }

  const handleCustomTime = (timeStr: string) => {
    if (!timeStr) return
    const [hh, mm] = timeStr.split(':').map(Number)
    const d = new Date(dayAnchor)
    d.setHours(hh, mm, 0, 0)
    onChange(d)
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {PRESETS.map((preset) => {
          const isCustom = 'label' in preset && preset.label === 'Custom'
          const isActive = isCustom ? showCustom : false
          return (
            <button
              key={preset.label}
              type="button"
              onClick={() => handlePreset(preset)}
              className={cn(
                'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
                isActive
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'border-border bg-background text-muted-foreground hover:bg-muted hover:text-foreground',
              )}
            >
              {preset.label}
            </button>
          )
        })}
        {value && !showCustom && (
          <span className="flex items-center px-1 text-xs text-muted-foreground">
            {formatHHMM(value)}
          </span>
        )}
      </div>

      {showCustom && (
        <div className="flex items-center gap-2">
          <input
            type="time"
            defaultValue={value ? toTimeInputValue(value) : toTimeInputValue(new Date())}
            onChange={(e) => handleCustomTime(e.target.value)}
            className="rounded-md border border-border bg-background px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
          />
          {value && (
            <span className="text-xs text-muted-foreground">{formatHHMM(value)}</span>
          )}
        </div>
      )}
    </div>
  )
}

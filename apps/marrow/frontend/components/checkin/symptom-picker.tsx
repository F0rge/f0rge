'use client'

import { Loader2, X } from 'lucide-react'
import { nowHHMM } from '@f0rge/ui'
import { useSymptomCatalog } from '@/lib/api/hooks'
import type { SymptomEvent } from '@/lib/api/types'

interface SymptomPickerProps {
  value: Record<string, number>
  onChange: (value: Record<string, number>) => void
  events: SymptomEvent[]
  onEventsChange: (events: SymptomEvent[]) => void
}

const SEVERITY_VALUES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

function stamp(key: string, severity: number): SymptomEvent {
  return { key, severity, time: nowHHMM() }
}

export function SymptomPicker({
  value,
  onChange,
  events,
  onEventsChange,
}: SymptomPickerProps) {
  const { data: catalog = [], isLoading } = useSymptomCatalog(false)
  const active = catalog.filter((c) => !c.archived)

  const toggle = (key: string) => {
    if (key in value) {
      const next = { ...value }
      delete next[key]
      onChange(next)
      onEventsChange(events.filter((e) => e.key !== key))
      return
    }
    onChange({ ...value, [key]: 5 })
    onEventsChange([...events, stamp(key, 5)])
  }

  const setSeverity = (key: string, severity: number) => {
    onChange({ ...value, [key]: severity })
    onEventsChange([...events, stamp(key, severity)])
  }

  const logNow = (key: string) => {
    const severity = value[key]
    if (severity === undefined) return
    onEventsChange([...events, stamp(key, severity)])
  }

  const removeEvent = (index: number) => {
    onEventsChange(events.filter((_, i) => i !== index))
  }

  return (
    <div className="space-y-3">
      <label className="text-sm font-semibold">Custom symptoms</label>
      <p className="text-xs text-muted-foreground">
        Tap a number to stamp the time. Log now keeps the same score at a new time.
      </p>

      {isLoading && (
        <div className="flex items-center justify-center py-4 text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
        </div>
      )}

      {!isLoading && (
        <div className="space-y-2">
          {active.map((symptom) => {
            const selected = symptom.key in value
            const severity = value[symptom.key]
            const stamps = events
              .map((event, index) => ({ event, index }))
              .filter(({ event }) => event.key === symptom.key)
            return (
              <div key={symptom.key}>
                <button
                  type="button"
                  aria-pressed={selected}
                  onClick={() => toggle(symptom.key)}
                  className={`min-h-[48px] w-full rounded-xl border px-3 py-2.5 text-left text-sm font-medium transition-all ${
                    selected
                      ? 'border-primary bg-primary text-primary-foreground shadow-sm'
                      : 'border-border bg-background text-muted-foreground'
                  }`}
                >
                  {symptom.label}
                  {selected && (
                    <span className="ml-2 text-primary-foreground/70">
                      {severity}/10
                    </span>
                  )}
                </button>

                {selected && (
                  <div className="mt-1.5 space-y-1.5">
                    <div className="overflow-x-auto scrollbar-thin px-0.5 pb-1">
                      <div className="flex gap-1">
                        {SEVERITY_VALUES.map((v) => (
                          <button
                            key={v}
                            type="button"
                            aria-label={`Severity ${v}`}
                            onClick={() => setSeverity(symptom.key, v)}
                            className={`min-h-[36px] min-w-[34px] flex-shrink-0 rounded-lg border text-xs font-semibold transition-all ${
                              severity === v
                                ? 'border-primary bg-primary text-primary-foreground'
                                : 'border-border bg-background text-muted-foreground'
                            }`}
                          >
                            {v}
                          </button>
                        ))}
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => logNow(symptom.key)}
                      className="min-h-[44px] w-full rounded-lg border border-border bg-background px-3 text-left text-xs font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
                    >
                      Log now · {severity}/10
                    </button>
                    {stamps.map(({ event, index }) => (
                      <div
                        key={`${event.time ?? 'na'}-${index}`}
                        className="flex items-center gap-2 rounded-lg border border-border bg-background px-2.5 py-2"
                      >
                        <span className="min-w-0 flex-1 text-sm">
                          <span className="font-medium tabular-nums">{event.severity}/10</span>
                          {event.time ? (
                            <span className="ml-2 text-muted-foreground">{event.time}</span>
                          ) : null}
                        </span>
                        <button
                          type="button"
                          aria-label="Remove stamp"
                          onClick={() => removeEvent(index)}
                          className="flex size-11 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground"
                        >
                          <X className="size-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

'use client'

import { X } from 'lucide-react'
import {
  Button,
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
  Field,
  FieldDescription,
  FieldTitle,
  Frame,
  FramePanel,
  Skeleton,
  ToggleGroup,
  ToggleGroupItem,
  cn,
  nowHHMM,
} from '@f0rge/ui'
import { useSymptomCatalog } from '@/lib/api/hooks'
import type { SymptomEvent } from '@/lib/api/types'

interface SymptomPickerProps {
  value: Record<string, number>
  onChange: (value: Record<string, number>) => void
  events: SymptomEvent[]
  onEventsChange: (events: SymptomEvent[]) => void
}

const SEVERITY_VALUES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

const severityItemClass =
  'min-h-[36px] min-w-0 flex-1 justify-center text-xs font-semibold tabular-nums data-[state=on]:bg-primary data-[state=on]:text-primary-foreground'

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
  }

  const setSeverity = (key: string, severity: number) => {
    onChange({ ...value, [key]: severity })
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
    <Field className="gap-3">
      <FieldTitle className="text-sm font-semibold">Custom symptoms</FieldTitle>
      <FieldDescription>
        The score is for the whole day. Tap Log now to record a flare at the current time.
      </FieldDescription>

      {isLoading && (
        <div className="space-y-2" aria-busy="true">
          <Skeleton className="h-12 w-full rounded-xl" />
          <Skeleton className="h-12 w-full rounded-xl" />
        </div>
      )}

      {!isLoading && active.length === 0 && (
        <Empty className="border-border py-8">
          <EmptyHeader>
            <EmptyTitle>No symptoms configured</EmptyTitle>
            <EmptyDescription>Add symptoms in Customize to track them here.</EmptyDescription>
          </EmptyHeader>
        </Empty>
      )}

      {!isLoading && active.length > 0 && (
        <Frame spacing="xs" variant="ghost" className="w-full">
          {active.map((symptom) => {
            const selected = symptom.key in value
            const severity = value[symptom.key]
            const stamps = events
              .map((event, index) => ({ event, index }))
              .filter(({ event }) => event.key === symptom.key)
            return (
              <FramePanel key={symptom.key} className="space-y-2 p-0">
                <button
                  type="button"
                  aria-pressed={selected}
                  onClick={() => toggle(symptom.key)}
                  className={cn(
                    'min-h-[48px] w-full rounded-xl border px-3 py-2.5 text-left text-sm font-medium transition-all',
                    selected
                      ? 'border-primary bg-primary text-primary-foreground shadow-sm'
                      : 'border-border bg-background text-muted-foreground',
                  )}
                >
                  {symptom.label}
                  {selected && (
                    <span className="ml-2 text-primary-foreground/70">{severity}/10</span>
                  )}
                </button>

                {selected && (
                  <div className="space-y-1.5 px-0.5 pb-2">
                    <ToggleGroup
                      spacing={1}
                      variant="outline"
                      value={[String(severity)]}
                      onValueChange={(next) => {
                        const picked = next[0]
                        if (picked == null) return
                        setSeverity(symptom.key, Number(picked))
                      }}
                      aria-label={`Severity for ${symptom.label}`}
                      className="grid w-full grid-cols-6 gap-1"
                    >
                      {SEVERITY_VALUES.map((v) => (
                        <ToggleGroupItem
                          key={v}
                          value={String(v)}
                          aria-label={`Severity ${v}`}
                          className={severityItemClass}
                        >
                          {v}
                        </ToggleGroupItem>
                      ))}
                    </ToggleGroup>
                    <Button
                      type="button"
                      variant="outline"
                      className="min-h-[44px] w-full justify-start text-xs font-medium text-muted-foreground"
                      onClick={() => logNow(symptom.key)}
                    >
                      Log now · {severity}/10
                    </Button>
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
              </FramePanel>
            )
          })}
        </Frame>
      )}
    </Field>
  )
}

'use client'

import { Loader2 } from 'lucide-react'
import { useSymptomCatalog } from '@/lib/api/hooks'

interface SymptomPickerProps {
  value: Record<string, number> // {key: severity 0-10} for each selected symptom
  onChange: (value: Record<string, number>) => void
}

const SEVERITY_VALUES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

export function SymptomPicker({ value, onChange }: SymptomPickerProps) {
  const { data: catalog = [], isLoading } = useSymptomCatalog(false)

  const active = catalog.filter((c) => !c.archived)

  const toggle = (key: string) => {
    if (key in value) {
      // Deselect: remove from dict
      const next = { ...value }
      delete next[key]
      onChange(next)
    } else {
      // Select: add with default severity 5
      onChange({ ...value, [key]: 5 })
    }
  }

  const setSeverity = (key: string, severity: number) => {
    onChange({ ...value, [key]: severity })
  }

  return (
    <div className="space-y-3">
      <label className="text-sm font-semibold">Custom symptoms</label>

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
                  <div className="mt-1.5 overflow-x-auto scrollbar-thin px-0.5 pb-1">
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
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

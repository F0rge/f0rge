'use client'

import { Loader2 } from 'lucide-react'
import type { SupplementCatalogItem, SymptomCatalogItem } from '@/lib/api/types'

const SEVERITY_VALUES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

interface CheckinDefaultsFormProps {
  supplements: SupplementCatalogItem[]
  symptoms: SymptomCatalogItem[]
  supplementsLoading: boolean
  symptomsLoading: boolean
  selectedSupplements: string[]
  onSupplementsChange: (keys: string[]) => void
  symptomDefaults: Record<string, number>
  onSymptomDefaultsChange: (value: Record<string, number>) => void
}

export function CheckinDefaultsForm({
  supplements,
  symptoms,
  supplementsLoading,
  symptomsLoading,
  selectedSupplements,
  onSupplementsChange,
  symptomDefaults,
  onSymptomDefaultsChange,
}: CheckinDefaultsFormProps) {
  const selectedSuppSet = new Set(selectedSupplements)

  const toggleSupplement = (key: string) => {
    const next = selectedSuppSet.has(key)
      ? selectedSupplements.filter((k) => k !== key)
      : [...selectedSupplements, key]
    onSupplementsChange(next)
  }

  const toggleSymptom = (key: string) => {
    if (key in symptomDefaults) {
      const next = { ...symptomDefaults }
      delete next[key]
      onSymptomDefaultsChange(next)
    } else {
      onSymptomDefaultsChange({ ...symptomDefaults, [key]: 5 })
    }
  }

  const setSeverity = (key: string, severity: number) => {
    onSymptomDefaultsChange({ ...symptomDefaults, [key]: severity })
  }

  return (
    <div className="space-y-8">
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Supplements</h2>
          {!supplementsLoading && supplements.length > 0 && (
            <div className="flex gap-3 text-xs">
              <button
                type="button"
                onClick={() => onSupplementsChange(supplements.map((s) => s.key))}
                className="text-muted-foreground underline"
              >
                All
              </button>
              <button
                type="button"
                onClick={() => onSupplementsChange([])}
                className="text-muted-foreground underline"
              >
                None
              </button>
            </div>
          )}
        </div>

        {supplementsLoading && (
          <div className="flex items-center justify-center py-4 text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
          </div>
        )}

        {!supplementsLoading && supplements.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No active supplements in your catalog. Add some under Catalogs first.
          </p>
        )}

        {!supplementsLoading && supplements.length > 0 && (
          <>
            {selectedSupplements.length === 0 && (
              <p className="mb-2 text-sm text-muted-foreground">
                None selected — empty days start with no supplements checked.
              </p>
            )}
            <div className="grid grid-cols-3 gap-2">
              {supplements.map((supp) => {
                const selected = selectedSuppSet.has(supp.key)
                return (
                  <button
                    key={supp.key}
                    type="button"
                    aria-pressed={selected}
                    onClick={() => toggleSupplement(supp.key)}
                    className={[
                      'min-h-[48px] w-full rounded-xl border px-2 py-2.5 text-sm font-medium transition-all',
                      selected
                        ? 'border-primary bg-primary text-primary-foreground shadow-sm'
                        : 'border-border bg-background text-muted-foreground',
                    ].join(' ')}
                  >
                    {supp.label}
                  </button>
                )
              })}
            </div>
          </>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold">Symptoms</h2>

        {symptomsLoading && (
          <div className="flex items-center justify-center py-4 text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
          </div>
        )}

        {!symptomsLoading && symptoms.length === 0 && (
          <p className="text-sm text-muted-foreground">
            No active symptoms in your catalog. Add some under Custom symptoms first.
          </p>
        )}

        {!symptomsLoading && symptoms.length > 0 && (
          <div className="space-y-2">
            {symptoms.map((symptom) => {
              const selected = symptom.key in symptomDefaults
              const severity = symptomDefaults[symptom.key]
              return (
                <div key={symptom.key}>
                  <button
                    type="button"
                    aria-pressed={selected}
                    onClick={() => toggleSymptom(symptom.key)}
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
                    <div className="mt-1.5 overflow-x-auto px-0.5 pb-1">
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
      </section>
    </div>
  )
}

'use client'

import { useState } from 'react'
import { Loader2, Pencil, Plus, X } from 'lucide-react'
import { toast } from 'sonner'
import {
  useSymptomCatalog,
  useAddSymptomCatalogItem,
  useUpdateSymptomCatalogItem,
} from '@/lib/api/hooks'
import type { SymptomCatalogItem } from '@/lib/api/types'

interface SymptomPickerProps {
  value: Record<string, number> // {key: severity 0-10} for each selected symptom
  onChange: (value: Record<string, number>) => void
}

function normalizeKey(raw: string): string {
  return raw
    .trim()
    .toLowerCase()
    .replace(/[-\s]+/g, '_')
    .replace(/[^a-z0-9_]/g, '')
}

const SEVERITY_VALUES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

export function SymptomPicker({ value, onChange }: SymptomPickerProps) {
  const { data: catalog = [], isLoading } = useSymptomCatalog(true)
  const addItem = useAddSymptomCatalogItem()
  const updateItem = useUpdateSymptomCatalogItem()

  const [manageMode, setManageMode] = useState(false)
  const [adding, setAdding] = useState(false)
  const [newLabel, setNewLabel] = useState('')

  const active = catalog.filter((c) => !c.archived)
  const archived = catalog.filter((c) => c.archived)

  const computeSuggestions = (): SymptomCatalogItem[] => {
    const q = newLabel.trim().toLowerCase()
    if (!q) return []
    const inputKey = normalizeKey(newLabel)
    return catalog.filter(
      (item) =>
        item.key.includes(inputKey) || item.label.toLowerCase().includes(q),
    )
  }
  const suggestions = computeSuggestions()

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

  const handleArchive = async (item: SymptomCatalogItem) => {
    try {
      await updateItem.mutateAsync({
        key: item.key,
        data: { archived: !item.archived },
      })
      if (!item.archived && item.key in value) {
        // Remove from today's selection when archiving
        const next = { ...value }
        delete next[item.key]
        onChange(next)
      }
    } catch {
      toast.error('Failed to update symptom')
    }
  }

  const handleAdd = async (existing?: SymptomCatalogItem) => {
    try {
      if (existing) {
        if (existing.archived) {
          await updateItem.mutateAsync({
            key: existing.key,
            data: { archived: false },
          })
        }
        // Auto-select on add; Restore does NOT auto-select
        if (!(existing.key in value)) {
          onChange({ ...value, [existing.key]: 5 })
        }
      } else {
        const label = newLabel.trim()
        if (!label) return
        const key = normalizeKey(label)
        if (!key) {
          toast.error('Name must contain letters or numbers')
          return
        }
        const created = await addItem.mutateAsync({ key, label })
        if (!(created.key in value)) {
          onChange({ ...value, [created.key]: 5 })
        }
      }
      setNewLabel('')
      setAdding(false)
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to add symptom'
      toast.error(msg)
    }
  }

  const handleRestore = async (item: SymptomCatalogItem) => {
    try {
      await updateItem.mutateAsync({
        key: item.key,
        data: { archived: false },
      })
      // Restore does NOT auto-select — user decides if it applies today
    } catch {
      toast.error('Failed to restore symptom')
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-sm font-semibold">Custom symptoms</label>
        <div className="flex gap-3 text-xs">
          <button
            type="button"
            onClick={() => {
              const next = Object.fromEntries(
                active.map((s) => [s.key, value[s.key] ?? 5]),
              )
              onChange(next)
            }}
            className="text-muted-foreground underline"
          >
            All
          </button>
          <button
            type="button"
            onClick={() => onChange({})}
            className="text-muted-foreground underline"
          >
            None
          </button>
          <button
            type="button"
            onClick={() => setManageMode((m) => !m)}
            className={`underline ${
              manageMode ? 'text-primary' : 'text-muted-foreground'
            }`}
          >
            {manageMode ? 'Done' : 'Manage'}
          </button>
        </div>
      </div>

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
                  onClick={() =>
                    manageMode ? handleArchive(symptom) : toggle(symptom.key)
                  }
                  className={`min-h-[48px] w-full rounded-xl border px-3 py-2.5 text-left text-sm font-medium transition-all ${
                    manageMode
                      ? 'border-destructive/40 bg-background text-destructive'
                      : selected
                        ? 'border-primary bg-primary text-primary-foreground shadow-sm'
                        : 'border-border bg-background text-muted-foreground'
                  }`}
                >
                  {manageMode ? `Archive: ${symptom.label}` : symptom.label}
                  {selected && !manageMode && (
                    <span className="ml-2 text-primary-foreground/70">
                      {severity}/10
                    </span>
                  )}
                </button>

                {selected && !manageMode && (
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

          {!manageMode && (
            <button
              type="button"
              onClick={() => setAdding(true)}
              className="flex min-h-[48px] w-full items-center justify-center gap-1.5 rounded-xl border border-dashed border-border bg-background px-3 py-2.5 text-sm font-medium text-muted-foreground hover:bg-muted"
            >
              <Plus className="size-4" />
              Add
            </button>
          )}
        </div>
      )}

      {manageMode && archived.length > 0 && (
        <div className="space-y-2 rounded-xl border border-border bg-muted/40 p-3">
          <p className="text-xs font-semibold text-muted-foreground">Archived</p>
          <div className="grid grid-cols-2 gap-2">
            {archived.map((symptom) => (
              <button
                key={symptom.key}
                type="button"
                onClick={() => handleRestore(symptom)}
                className="min-h-[44px] rounded-xl border border-border bg-background px-2 py-2 text-xs font-medium text-muted-foreground"
              >
                <Pencil className="mr-1 inline size-3" />
                Restore: {symptom.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {adding && (
        <div className="space-y-2 rounded-xl border border-border bg-muted/40 p-3">
          <label className="text-xs font-semibold text-muted-foreground">
            Add symptom
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={newLabel}
              onChange={(e) => setNewLabel(e.target.value)}
              placeholder="e.g. Headache"
              autoFocus
              className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <button
              type="button"
              onClick={() => handleAdd()}
              disabled={!newLabel.trim() || addItem.isPending}
              className="min-h-[40px] rounded-lg bg-primary px-3 text-sm font-semibold text-primary-foreground disabled:opacity-50"
            >
              {addItem.isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                'Add'
              )}
            </button>
            <button
              type="button"
              onClick={() => {
                setAdding(false)
                setNewLabel('')
              }}
              className="flex size-10 items-center justify-center rounded-lg border border-border bg-background"
            >
              <X className="size-4" />
            </button>
          </div>
          {suggestions.length > 0 && (
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">
                Used previously — tap to re-add (keeps category consistent):
              </p>
              <div className="flex flex-wrap gap-1.5">
                {suggestions.map((s) => (
                  <button
                    key={s.key}
                    type="button"
                    onClick={() => handleAdd(s)}
                    className="rounded-full border border-border bg-background px-2.5 py-1 text-xs text-foreground hover:bg-muted"
                  >
                    {s.label}
                    {s.archived ? ' (archived)' : ''}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

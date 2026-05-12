'use client'

import { useState } from 'react'
import { Loader2, Pencil, Plus, X } from 'lucide-react'
import { toast } from 'sonner'
import {
  useSupplementCatalog,
  useAddSupplementCatalogItem,
  useUpdateSupplementCatalogItem,
} from '@/lib/api/hooks'
import type { SupplementCatalogItem } from '@/lib/api/types'

interface SupplementPickerProps {
  value: string // comma-separated supplement keys
  onChange: (value: string) => void
}

function normalizeKey(raw: string): string {
  return raw
    .trim()
    .toLowerCase()
    .replace(/[-\s]+/g, '_')
    .replace(/[^a-z0-9_]/g, '')
}

export function SupplementPicker({ value, onChange }: SupplementPickerProps) {
  const { data: catalog = [], isLoading } = useSupplementCatalog(true)
  const addItem = useAddSupplementCatalogItem()
  const updateItem = useUpdateSupplementCatalogItem()

  const [manageMode, setManageMode] = useState(false)
  const [adding, setAdding] = useState(false)
  const [newLabel, setNewLabel] = useState('')

  const selectedKeys = new Set(
    value.split(',').map((s) => s.trim()).filter(Boolean),
  )

  const active = catalog.filter((c) => !c.archived)
  const archived = catalog.filter((c) => c.archived)

  const computeSuggestions = (): SupplementCatalogItem[] => {
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
    const current = value
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    const next = current.includes(key)
      ? current.filter((s) => s !== key)
      : [...current, key]
    onChange(next.join(','))
  }

  const handleArchive = async (item: SupplementCatalogItem) => {
    try {
      await updateItem.mutateAsync({
        key: item.key,
        data: { archived: !item.archived },
      })
      if (!item.archived && selectedKeys.has(item.key)) {
        // Removing from active should drop it from the current day's selection.
        const next = value
          .split(',')
          .map((s) => s.trim())
          .filter((s) => s && s !== item.key)
        onChange(next.join(','))
      }
    } catch {
      toast.error('Failed to update supplement')
    }
  }

  const handleAdd = async (existing?: SupplementCatalogItem) => {
    try {
      if (existing) {
        if (existing.archived) {
          await updateItem.mutateAsync({
            key: existing.key,
            data: { archived: false },
          })
        }
        // Auto-select on add/restore.
        const current = value
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean)
        if (!current.includes(existing.key)) {
          onChange([...current, existing.key].join(','))
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
        const current = value
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean)
        if (!current.includes(created.key)) {
          onChange([...current, created.key].join(','))
        }
      }
      setNewLabel('')
      setAdding(false)
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to add supplement'
      toast.error(msg)
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <label className="text-sm font-semibold">Supplements taken</label>
        <div className="flex gap-3 text-xs">
          <button
            type="button"
            onClick={() => {
              const allActive = active.map((s) => s.key).join(',')
              onChange(allActive)
            }}
            className="text-muted-foreground underline"
          >
            All
          </button>
          <button
            type="button"
            onClick={() => onChange('')}
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
        <div className="grid grid-cols-3 gap-2">
          {active.map((supp) => {
            const taken = selectedKeys.has(supp.key)
            return (
              <div key={supp.key} className="relative">
                <button
                  type="button"
                  onClick={() =>
                    manageMode ? handleArchive(supp) : toggle(supp.key)
                  }
                  className={`min-h-[48px] w-full rounded-xl border px-2 py-2.5 text-sm font-medium transition-all ${
                    manageMode
                      ? 'border-destructive/40 bg-background text-destructive'
                      : taken
                        ? 'border-primary bg-primary text-primary-foreground shadow-sm'
                        : 'border-border bg-background text-muted-foreground'
                  }`}
                >
                  {manageMode ? `Archive: ${supp.label}` : supp.label}
                </button>
              </div>
            )
          })}

          {!manageMode && (
            <button
              type="button"
              onClick={() => setAdding(true)}
              className="flex min-h-[48px] items-center justify-center gap-1.5 rounded-xl border border-dashed border-border bg-background px-2 py-2.5 text-sm font-medium text-muted-foreground hover:bg-muted"
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
          <div className="grid grid-cols-3 gap-2">
            {archived.map((supp) => (
              <button
                key={supp.key}
                type="button"
                onClick={() => handleArchive(supp)}
                className="min-h-[44px] rounded-xl border border-border bg-background px-2 py-2 text-xs font-medium text-muted-foreground"
              >
                <Pencil className="mr-1 inline size-3" />
                Restore: {supp.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {adding && (
        <div className="space-y-2 rounded-xl border border-border bg-muted/40 p-3">
          <label className="text-xs font-semibold text-muted-foreground">
            Add supplement
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={newLabel}
              onChange={(e) => setNewLabel(e.target.value)}
              placeholder="e.g. Quercetin"
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

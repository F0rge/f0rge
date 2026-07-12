'use client'

import { useState } from 'react'
import { Loader2, Plus, X } from 'lucide-react'
import { toast } from 'sonner'
import { useMarkerCatalog, useCreateMarker } from '@/lib/api/hooks'
import { handleMutationError } from '@f0rge/ui/api'
import type { LabMarkerCatalog } from '@/lib/api/types'

interface MarkerPickerProps {
  value: string // display text shown in the input
  catalogId?: number | null
  onSelect: (canonical: string, catalogId: number) => void
}

function normalizeCanonical(raw: string): string {
  return raw
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, '_')
    .replace(/[^a-z0-9_]/g, '')
}

export function MarkerPicker({ value, onSelect }: MarkerPickerProps) {
  const [query, setQuery] = useState(value)
  const [adding, setAdding] = useState(false)

  const { data: catalog = [], isLoading } = useMarkerCatalog(query.length >= 1 ? query : undefined)
  const createMarker = useCreateMarker()

  const suggestions = catalog.filter(
    (item) =>
      item.canonical_name.includes(normalizeCanonical(query)) ||
      item.display_name.toLowerCase().includes(query.toLowerCase()),
  )

  const exactMatch = catalog.find(
    (item) => item.canonical_name === normalizeCanonical(query),
  )

  function handleSelect(item: LabMarkerCatalog) {
    setQuery(item.display_name)
    setAdding(false)
    onSelect(item.canonical_name, item.id)
  }

  async function handleCreate() {
    const label = query.trim()
    if (!label) return
    const canonical = normalizeCanonical(label)
    if (!canonical) {
      toast.error('Name must contain letters or numbers')
      return
    }
    try {
      const created = await createMarker.mutateAsync({
        canonical_name: canonical,
        display_name: label,
      })
      setQuery(created.display_name)
      setAdding(false)
      onSelect(created.canonical_name, created.id)
    } catch (err) {
      handleMutationError(err, 'Failed to create marker')
    }
  }

  return (
    <div className="relative">
      <div className="flex gap-1">
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setAdding(true)
          }}
          onFocus={() => setAdding(true)}
          placeholder="Search or create marker..."
          className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
        {query && (
          <button
            type="button"
            onClick={() => {
              setQuery('')
              setAdding(false)
            }}
            className="flex size-9 items-center justify-center rounded-lg border border-border bg-background"
          >
            <X className="size-3.5 text-muted-foreground" />
          </button>
        )}
      </div>

      {adding && query.length >= 1 && (
        <div className="absolute left-0 right-0 top-full z-10 mt-1 max-h-48 overflow-y-auto rounded-lg border border-border bg-background shadow-md">
          {isLoading ? (
            <div className="flex items-center justify-center py-3">
              <Loader2 className="size-4 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <>
              {suggestions.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onMouseDown={(e) => {
                    e.preventDefault()
                    handleSelect(item)
                  }}
                  className="w-full px-3 py-2 text-left text-sm hover:bg-muted"
                >
                  <span className="font-medium">{item.display_name}</span>
                  <span className="ml-1.5 text-xs text-muted-foreground">
                    {item.canonical_name}
                  </span>
                </button>
              ))}
              {!exactMatch && query.trim() && (
                <button
                  type="button"
                  onMouseDown={(e) => {
                    e.preventDefault()
                    handleCreate()
                  }}
                  disabled={createMarker.isPending}
                  className="flex w-full items-center gap-1.5 border-t border-border px-3 py-2 text-left text-sm text-primary hover:bg-muted disabled:opacity-50"
                >
                  {createMarker.isPending ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <Plus className="size-3.5" />
                  )}
                  Create &quot;{query.trim()}&quot;
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

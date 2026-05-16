'use client'

import { useState, useEffect } from 'react'
import { Loader2, FlaskConical } from 'lucide-react'
import { useMarkerCatalog } from '@/lib/api/hooks'
import { MarkerHistoryChart } from './marker-history-chart'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import type { LabMarkerCatalog } from '@/lib/api/types'

export function MarkerList() {
  const [search, setSearch] = useState('')
  const [debounced, setDebounced] = useState('')
  const [selected, setSelected] = useState<LabMarkerCatalog | null>(null)

  useEffect(() => {
    const t = setTimeout(() => setDebounced(search), 300)
    return () => clearTimeout(t)
  }, [search])

  const { data: catalog = [], isLoading, isError } = useMarkerCatalog(debounced || undefined)

  return (
    <div className="space-y-3">
      <input
        type="search"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search markers..."
        className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
      />

      {isLoading && (
        <div className="flex justify-center py-8">
          <Loader2 className="size-5 animate-spin text-muted-foreground" />
        </div>
      )}

      {isError && (
        <p className="py-4 text-sm text-destructive">Failed to load marker catalog.</p>
      )}

      {!isLoading && !isError && catalog.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-12">
          <FlaskConical className="size-10 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">
            {debounced ? 'No markers match your search.' : 'No markers in catalog yet.'}
          </p>
        </div>
      )}

      {!isLoading && !isError && catalog.length > 0 && (
        <div className="space-y-1">
          {catalog.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setSelected(item)}
              className="w-full rounded-lg border border-border bg-card px-4 py-3 text-left transition-colors hover:bg-muted/50"
            >
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-medium">{item.display_name}</p>
                  <p className="text-xs text-muted-foreground">{item.canonical_name}</p>
                </div>
                {item.common_units.length > 0 && (
                  <span className="text-xs text-muted-foreground">
                    {item.common_units[0]}
                  </span>
                )}
              </div>
            </button>
          ))}
        </div>
      )}

      <Dialog open={!!selected} onOpenChange={(o) => { if (!o) setSelected(null) }}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>{selected?.display_name ?? ''}</DialogTitle>
          </DialogHeader>
          {selected && (
            <MarkerHistoryChart
              canonicalName={selected.canonical_name}
              displayName={selected.display_name}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}

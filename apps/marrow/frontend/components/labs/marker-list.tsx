'use client'

import { useState, useEffect, useMemo } from 'react'
import { Loader2, FlaskConical } from 'lucide-react'
import { useMarkerCatalog } from '@/lib/api/hooks'
import { MarkerHistoryChart } from './marker-history-chart'
import type { LabMarkerCatalog } from '@/lib/api/types'
import {
  Autocomplete,
  AutocompleteContent,
  AutocompleteEmpty,
  AutocompleteInput,
  AutocompleteItem,
  AutocompleteList,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
  FetchError,
  Field,
  FieldLabel,
  Item,
  ItemContent,
  ItemDescription,
  ItemGroup,
  ItemHeader,
  ItemTitle,
} from '@f0rge/ui'

export function MarkerList() {
  const [search, setSearch] = useState('')
  const [debounced, setDebounced] = useState('')
  const [selected, setSelected] = useState<LabMarkerCatalog | null>(null)

  useEffect(() => {
    const t = setTimeout(() => setDebounced(search), 300)
    return () => clearTimeout(t)
  }, [search])

  const { data: catalog = [], isLoading, isError, refetch } = useMarkerCatalog(debounced || undefined)

  const itemLabels = useMemo(() => catalog.map((item) => item.display_name), [catalog])

  const catalogByLabel = useMemo(
    () => new Map(catalog.map((item) => [item.display_name, item])),
    [catalog],
  )

  function handlePick(label: string | null) {
    if (!label) return
    const item = catalogByLabel.get(label)
    if (item) setSelected(item)
  }

  return (
    <div className="space-y-3">
      <Field>
        <FieldLabel>Search markers</FieldLabel>
        <Autocomplete items={itemLabels}>
          <AutocompleteInput
            placeholder="Search markers..."
            showClear
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <AutocompleteContent>
            <AutocompleteList>
              {(label: string) => (
                <AutocompleteItem key={label} value={label} onClick={() => handlePick(label)}>
                  {label}
                </AutocompleteItem>
              )}
            </AutocompleteList>
            <AutocompleteEmpty>No markers match</AutocompleteEmpty>
          </AutocompleteContent>
        </Autocomplete>
      </Field>

      {isLoading && (
        <div className="flex justify-center py-8">
          <Loader2 className="size-5 animate-spin text-muted-foreground" />
        </div>
      )}

      {isError && (
        <FetchError message="Failed to load marker catalog." onRetry={() => refetch()} />
      )}

      {!isLoading && !isError && catalog.length === 0 && (
        <Empty className="border-border py-12">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <FlaskConical />
            </EmptyMedia>
            <EmptyTitle>{debounced ? 'No matches' : 'No markers yet'}</EmptyTitle>
            <EmptyDescription>
              {debounced ? 'Try a different search term.' : 'Markers appear as you add lab results.'}
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      )}

      {!isLoading && !isError && catalog.length > 0 && (
        <ItemGroup className="gap-2">
          {catalog.map((item) => (
            <Item
              key={item.id}
              variant="outline"
              className="cursor-pointer rounded-xl bg-card hover:bg-muted/50"
              render={<button type="button" onClick={() => setSelected(item)} />}
            >
              <ItemContent>
                <ItemHeader>
                  <ItemTitle>{item.display_name}</ItemTitle>
                  {item.common_units.length > 0 && (
                    <span className="text-xs text-muted-foreground">{item.common_units[0]}</span>
                  )}
                </ItemHeader>
                <ItemDescription>{item.canonical_name}</ItemDescription>
              </ItemContent>
            </Item>
          ))}
        </ItemGroup>
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

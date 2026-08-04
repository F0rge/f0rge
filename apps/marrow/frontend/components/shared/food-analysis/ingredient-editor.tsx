'use client'

import { useRef, useState } from 'react'
import { useClampedHeightBelow, useFocusScrollIntoView } from '@/hooks/keyboard-viewport'
import { useKeyboardOpen } from '@/hooks/use-keyboard-open'
import { Loader2, Plus, Search } from 'lucide-react'
import { Button } from '@f0rge/ui'
import { Input } from '@f0rge/ui'
import { Badge } from '@f0rge/ui'
import { useAddIngredient, useIngredientCatalog } from '@/lib/api/hooks'
import { handleMutationError } from '@f0rge/ui/api'
import { useDebouncedValue } from '@f0rge/ui'
import { categoryLabel, highFodmapAxes } from '@/lib/ingredients'
import type { DietaryIngredient } from '@/lib/api/types'
import { cn } from '@f0rge/ui'

interface IngredientEditorProps {
  photoId: number
  existingNames: string[]
  onAdded: () => void
}

function CatalogBadges({ ing }: { ing: DietaryIngredient }) {
  const highFodmap = highFodmapAxes(ing)
  return (
    <div className="mt-0.5 flex flex-wrap items-center gap-1">
      <Badge variant="secondary" className="text-[10px]">
        {categoryLabel(ing.category)}
      </Badge>
      {ing.histamine_score != null && (
        <Badge variant="outline" className="text-[10px]">
          H:{ing.histamine_score}
        </Badge>
      )}
      {ing.contains_gluten && (
        <Badge variant="outline" className="text-[10px]">
          Gluten
        </Badge>
      )}
      {ing.contains_dairy && (
        <Badge variant="outline" className="text-[10px]">
          Dairy
        </Badge>
      )}
      {highFodmap.length > 0 && (
        <Badge variant="outline" className="text-[10px]">
          FODMAP↑ {highFodmap.join(', ')}
        </Badge>
      )}
    </div>
  )
}

function normalizeName(name: string): string {
  return name.trim().toLowerCase()
}

export function IngredientEditor({ photoId, existingNames, onAdded }: IngredientEditorProps) {
  const [adding, setAdding] = useState(false)
  const [searchInput, setSearchInput] = useState('')
  const searchAnchorRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const onFocusScroll = useFocusScrollIntoView()
  const keyboardOpen = useKeyboardOpen()
  const debouncedSearch = useDebouncedValue(searchInput, 300)
  const addIngredient = useAddIngredient()

  const searchReady = debouncedSearch.trim().length >= 2
  const { data: catalog = [], isLoading, isFetching } = useIngredientCatalog(
    debouncedSearch,
    false,
    { limit: 20, enabled: adding && searchReady },
  )

  const existingSet = new Set(existingNames.map(normalizeName))
  const trimmedQuery = searchInput.trim()
  const customAlreadyExists =
    trimmedQuery.length > 0 && existingSet.has(normalizeName(trimmedQuery))

  const reset = () => {
    setAdding(false)
    setSearchInput('')
  }

  const handleAdd = async (name: string) => {
    const trimmed = name.trim()
    if (!trimmed || existingSet.has(normalizeName(trimmed))) return
    try {
      await addIngredient.mutateAsync({ photoId, name: trimmed })
      reset()
      onAdded()
    } catch (err) {
      handleMutationError(err, 'Failed to add ingredient')
    }
  }

  const showSpinner = adding && searchReady && (isLoading || isFetching)
  const availableCatalog = catalog.filter(
    (ing) => !existingSet.has(normalizeName(ing.canonical_name)),
  )
  const showSuggestions = adding && searchReady && !showSpinner && availableCatalog.length > 0
  const listMaxHeight = useClampedHeightBelow(searchAnchorRef, {
    enabled: showSuggestions && keyboardOpen,
  })

  if (!adding) {
    return (
      <Button
        type="button"
        variant="outline"
        className="min-h-[44px] w-full justify-start gap-2 text-sm"
        onClick={() => {
          setAdding(true)
          requestAnimationFrame(() => searchRef.current?.focus())
        }}
      >
        <Plus className="size-4 shrink-0" />
        Add ingredient
      </Button>
    )
  }

  return (
    <div className="space-y-2 rounded-lg border border-border bg-muted/30 p-2">
      <div ref={searchAnchorRef} className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          ref={searchRef}
          type="search"
          value={searchInput}
          onFocus={onFocusScroll}
          onChange={(e) => setSearchInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Escape') {
              e.preventDefault()
              reset()
            }
          }}
          placeholder="Search ingredients (e.g. cheese)…"
          className="min-h-[44px] pl-9"
          autoFocus
          aria-label="Search ingredients"
        />
      </div>

      {trimmedQuery.length > 0 && trimmedQuery.length < 2 && (
        <p className="px-1 text-xs text-muted-foreground">Type at least 2 characters to search.</p>
      )}

      {showSpinner && (
        <div className="flex items-center justify-center py-3">
          <Loader2 className="size-5 animate-spin text-muted-foreground" />
        </div>
      )}

      {searchReady && !showSpinner && availableCatalog.length === 0 && (
        <p className="px-1 text-xs text-muted-foreground">No catalog matches.</p>
      )}

      {showSuggestions && (
        <ul
          className="max-h-64 space-y-1 overflow-y-auto"
          style={listMaxHeight != null ? { maxHeight: listMaxHeight } : undefined}
          aria-label="Ingredient suggestions"
        >
          {availableCatalog.map((ing) => (
            <li key={ing.id}>
              <button
                type="button"
                disabled={addIngredient.isPending}
                onClick={() => handleAdd(ing.canonical_name)}
                className={cn(
                  'min-h-[44px] w-full rounded-lg border border-border bg-background px-3 py-2 text-left transition-colors',
                  'hover:bg-muted/50 disabled:opacity-50',
                )}
              >
                <span className="text-sm font-medium capitalize">{ing.canonical_name}</span>
                <CatalogBadges ing={ing} />
              </button>
            </li>
          ))}
        </ul>
      )}

      {trimmedQuery.length > 0 && (
        <button
          type="button"
          disabled={addIngredient.isPending || customAlreadyExists}
          onClick={() => handleAdd(trimmedQuery)}
          className={cn(
            'min-h-[44px] w-full rounded-lg border border-dashed border-border px-3 py-2 text-left text-sm transition-colors',
            'hover:bg-muted/50 disabled:cursor-not-allowed disabled:opacity-50',
          )}
        >
          {customAlreadyExists
            ? `“${trimmedQuery}” is already on this meal`
            : `Add “${trimmedQuery}” as custom ingredient`}
        </button>
      )}

      <div className="flex justify-end">
        <Button
          type="button"
          variant="ghost"
          className="min-h-[44px]"
          onClick={reset}
          disabled={addIngredient.isPending}
        >
          Cancel
        </Button>
      </div>
    </div>
  )
}

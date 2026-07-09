'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Plus, Search } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { TierBanner } from '@/components/customize/tier-banner'
import { IngredientFormDialog } from '@/components/customize/ingredient-form-dialog'
import { PageShell } from '@/components/layout/page-shell'
import { useIngredientCatalog, useArchiveDietaryIngredient } from '@/lib/api/hooks'
import { handleMutationError } from '@/lib/api/client'
import type { DietaryIngredient } from '@/lib/api/types'
import { cn } from '@/lib/utils'
import { categoryLabel, highFodmapAxes } from '@/lib/ingredients'

// Debounce the search box so we don't fire a query per keystroke.
// setState runs inside setTimeout (deferred), so this does not trip
// react-hooks/set-state-in-effect.
function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(id)
  }, [value, delay])
  return debounced
}

// The catalogue holds a few hundred rows; with no search filter we cap what we
// render so an unfiltered view never paints hundreds of DOM nodes.
const RENDER_CAP = 50

function IngredientRow({
  ing,
  onEdit,
  onToggleArchive,
  archivePending,
}: {
  ing: DietaryIngredient
  onEdit: () => void
  onToggleArchive: () => void
  archivePending: boolean
}) {
  const highFodmap = highFodmapAxes(ing)
  return (
    <div className="flex items-center gap-3 rounded-lg border border-muted p-3">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              'truncate text-sm font-medium capitalize',
              ing.archived && 'text-muted-foreground line-through',
            )}
          >
            {ing.canonical_name}
          </span>
          {ing.archived && (
            <Badge variant="outline" className="shrink-0">
              Archived
            </Badge>
          )}
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-1">
          <Badge variant="secondary">{categoryLabel(ing.category)}</Badge>
          {ing.histamine_score != null && <Badge variant="outline">H:{ing.histamine_score}</Badge>}
          {ing.contains_gluten && <Badge variant="outline">Gluten</Badge>}
          {ing.contains_dairy && <Badge variant="outline">Dairy</Badge>}
          {highFodmap.length > 0 && (
            <Badge variant="outline">FODMAP↑ {highFodmap.join(', ')}</Badge>
          )}
          {ing.aliases.length > 0 && (
            <Badge variant="ghost">
              {ing.aliases.length} alias{ing.aliases.length > 1 ? 'es' : ''}
            </Badge>
          )}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1.5">
        <Button variant="outline" size="sm" className="min-h-[44px]" onClick={onEdit}>
          Edit
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className="min-h-[44px]"
          onClick={onToggleArchive}
          disabled={archivePending}
        >
          {ing.archived ? 'Restore' : 'Archive'}
        </Button>
      </div>
    </div>
  )
}

export default function IngredientsClient() {
  const [searchInput, setSearchInput] = useState('')
  const search = useDebouncedValue(searchInput, 300)
  const [includeArchived, setIncludeArchived] = useState(false)
  const [addOpen, setAddOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)

  const { data: ingredients = [], isLoading, isError } = useIngredientCatalog(search, includeArchived)
  const archive = useArchiveDietaryIngredient()

  const editing = editingId != null ? (ingredients.find((i) => i.id === editingId) ?? null) : null

  useEffect(() => {
    if (editingId != null && !isLoading && !isError && editing == null) {
      const id = setTimeout(() => setEditingId(null), 0)
      return () => clearTimeout(id)
    }
  }, [editingId, editing, isLoading, isError])

  const hasSearch = search.trim().length > 0
  const shown = hasSearch ? ingredients : ingredients.slice(0, RENDER_CAP)
  const hiddenCount = ingredients.length - shown.length

  function handleToggleArchive(ing: DietaryIngredient) {
    archive.mutate(
      { id: ing.id, archived: !ing.archived },
      { onError: (err) => handleMutationError(err, 'Failed to update ingredient') },
    )
  }

  return (
    <PageShell>
      {/* Header */}
      <div className="mb-6">
        <Link
          href="/customize"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Customize
        </Link>
        <div className="mt-3 flex items-center justify-between gap-2">
          <h1 className="text-xl font-semibold tracking-tight">Dietary ingredients</h1>
          <Button size="sm" className="min-h-[44px]" onClick={() => setAddOpen(true)}>
            <Plus className="size-4" />
            Add
          </Button>
        </div>
      </div>

      <TierBanner tier="catalog">
        Edit the FODMAP, histamine, gluten and dairy classifications used to score your meals.
        Ingredients can be archived (hidden) but not deleted, so past scores stay intact. Names
        can&apos;t be renamed — archive and add a new one instead.
      </TierBanner>

      {/* Search + show archived */}
      <div className="relative mt-4">
        <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder="Search ingredients (e.g. cheese)..."
          className="min-h-[44px] pl-9"
        />
      </div>
      <label className="mt-2 flex min-h-[44px] items-center gap-2 text-sm text-muted-foreground">
        <input
          type="checkbox"
          checked={includeArchived}
          onChange={(e) => setIncludeArchived(e.target.checked)}
          className="size-4 rounded border-border"
        />
        Show archived
      </label>

      {isError ? (
        <div className="mt-4 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          Couldn&apos;t load ingredients. Refresh the page to try again.
        </div>
      ) : isLoading ? (
        <div className="mt-4 flex flex-col gap-2">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-16 w-full animate-pulse rounded-lg bg-muted" />
          ))}
        </div>
      ) : shown.length === 0 ? (
        <p className="mt-6 text-center text-sm text-muted-foreground">
          {hasSearch ? `No ingredients match “${search.trim()}”.` : 'No ingredients yet.'}
        </p>
      ) : (
        <>
          {!hasSearch && hiddenCount > 0 && (
            <p className="mt-4 text-xs text-muted-foreground">
              Showing the first {RENDER_CAP} of {ingredients.length}. Search to find a specific
              ingredient.
            </p>
          )}
          <div className="mt-3 grid grid-cols-1 gap-2 lg:grid-cols-2">
            {shown.map((ing) => (
              <IngredientRow
                key={ing.id}
                ing={ing}
                onEdit={() => setEditingId(ing.id)}
                onToggleArchive={() => handleToggleArchive(ing)}
                archivePending={archive.isPending}
              />
            ))}
          </div>
        </>
      )}

      {/* Add dialog — key toggles on open so the form resets each time. */}
      <IngredientFormDialog
        key={addOpen ? 'add-open' : 'add-closed'}
        open={addOpen}
        onOpenChange={setAddOpen}
      />

      {/* Edit dialog — mounted only when an ingredient is selected; keyed by id
          so switching rows reseeds the form, but alias add/remove (same id) does not. */}
      {editing && (
        <IngredientFormDialog
          key={editing.id}
          open
          ingredient={editing}
          onOpenChange={(o) => {
            if (!o) setEditingId(null)
          }}
        />
      )}
    </PageShell>
  )
}

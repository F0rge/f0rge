'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { Loader2, Search } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@f0rge/ui'
import { Input } from '@f0rge/ui'
import type { RecentMeal } from '@/lib/api/types'
import { DietFlagPills } from './diet-flag-pills'
import { MealIconThumb, useMealThumbSrc } from './meal-icon-thumb'
import { useClampedHeightBelow, useFocusScrollIntoView } from '@/hooks/keyboard-viewport'
import { useKeyboardOpen } from '@/hooks/use-keyboard-open'

function ingredientPreview(ingredients: string[] | undefined): string {
  if (!ingredients || ingredients.length === 0) return ''
  const first = ingredients.slice(0, 3).join(' · ')
  const rest = ingredients.length - 3
  return rest > 0 ? `${first} +${rest}` : first
}

function matchesQuery(meal: RecentMeal, q: string): boolean {
  if (!q) return true
  if (meal.dish_name.toLowerCase().includes(q)) return true
  return (meal.ingredients ?? []).some((ing) => ing.toLowerCase().includes(q))
}

function RecentMealThumb({ meal, loading }: { meal: RecentMeal; loading: boolean }) {
  const { src, onError } = useMealThumbSrc(meal.source_photo_id)
  const showPhoto = meal.has_image !== false && src != null

  return (
    <div className="relative size-12 flex-none overflow-hidden rounded-lg bg-muted">
      {showPhoto ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt={meal.dish_name}
          className="size-full object-cover"
          loading="lazy"
          onError={onError}
        />
      ) : (
        <MealIconThumb
          iconKey={meal.icon_key ?? 'bowl'}
          size="md"
          className="size-full rounded-lg"
        />
      )}
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/40">
          <Loader2 className="size-4 animate-spin text-white" />
        </div>
      )}
    </div>
  )
}

interface LogAgainSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  meals: RecentMeal[]
  cloningId: number | null
  onClone: (meal: RecentMeal) => void
}

export function LogAgainSheet({ open, onOpenChange, meals, cloningId, onClone }: LogAgainSheetProps) {
  const [query, setQuery] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const searchAnchorRef = useRef<HTMLDivElement>(null)
  const onFocusScroll = useFocusScrollIntoView()
  const keyboardOpen = useKeyboardOpen()
  const listMaxHeight = useClampedHeightBelow(searchAnchorRef, {
    enabled: open && keyboardOpen,
    min: 140,
    max: 360,
  })

  const q = query.trim().toLowerCase()
  const filtered = useMemo(
    () => (q ? meals.filter((m) => matchesQuery(m, q)) : meals),
    [meals, q],
  )

  const handleOpenChange = (next: boolean) => {
    if (!next) {
      setQuery('')
    }
    onOpenChange(next)
  }

  // Re-focus search when the sheet opens so Esc/typing work immediately.
  useEffect(() => {
    if (!open) return
    const id = window.setTimeout(() => inputRef.current?.focus(), 50)
    return () => window.clearTimeout(id)
  }, [open])

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="flex max-h-[min(85vh,640px)] flex-col gap-3 sm:max-w-md">
        <DialogHeader className="pr-8">
          <DialogTitle>Log again</DialogTitle>
          <DialogDescription>
            Search by dish or ingredient, then tap to re-log — no photo, no re-analysis.
          </DialogDescription>
        </DialogHeader>

        <div ref={searchAnchorRef} className="relative shrink-0">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            ref={inputRef}
            autoFocus
            value={query}
            onFocus={onFocusScroll}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Escape') {
                if (query) {
                  e.stopPropagation()
                  setQuery('')
                }
                // Empty query: let Dialog handle Esc → close
              }
            }}
            placeholder="Search by dish or ingredient…"
            className="pl-9"
            enterKeyHint="search"
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
            aria-label="Search meals by dish or ingredient"
          />
        </div>

        <div
          className="-mx-1 min-h-0 flex-1 space-y-1.5 overflow-y-auto overscroll-contain px-1"
          style={{ maxHeight: listMaxHeight != null ? listMaxHeight : '55vh' }}
          role="listbox"
          aria-label="Matching meals"
        >
          {meals.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No meals to re-log yet. Confirm a meal analysis first.
            </p>
          ) : filtered.length === 0 ? (
            <div className="space-y-1 py-6 text-center">
              <p className="text-sm text-muted-foreground">
                No meals match &ldquo;{query.trim()}&rdquo;.
              </p>
              <p className="text-xs text-muted-foreground">
                Try a dish name or an ingredient (e.g. chicken, rice).
              </p>
            </div>
          ) : (
            filtered.map((meal) => {
              const preview = ingredientPreview(meal.ingredients)
              return (
                <button
                  key={meal.source_photo_id}
                  type="button"
                  role="option"
                  onClick={() => onClone(meal)}
                  disabled={cloningId !== null}
                  className="flex w-full items-center gap-3 rounded-xl border border-border bg-background p-2 text-left transition-colors hover:border-primary disabled:opacity-60"
                  aria-label={`Log ${meal.dish_name} again`}
                >
                  <RecentMealThumb meal={meal} loading={cloningId === meal.source_photo_id} />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium">{meal.dish_name}</div>
                    {preview ? (
                      <p className="mt-0.5 line-clamp-1 text-[10px] leading-tight text-muted-foreground">
                        {preview}
                      </p>
                    ) : null}
                    <div className="mt-0.5 flex flex-wrap items-center gap-2">
                      <span className="text-xs text-muted-foreground">
                        {meal.times_logged > 1 ? `Logged ${meal.times_logged}×` : 'Logged once'}
                      </span>
                      <DietFlagPills flags={meal.diet_flags} />
                    </div>
                  </div>
                </button>
              )
            })
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

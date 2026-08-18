'use client'

import { useRef, useState } from 'react'
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
import { MealIconThumb, photoThumbSrc } from './meal-icon-thumb'
import { useClampedHeightBelow, useFocusScrollIntoView } from '@/hooks/keyboard-viewport'
import { useKeyboardOpen } from '@/hooks/use-keyboard-open'

function RecentMealThumb({ meal, loading }: { meal: RecentMeal; loading: boolean }) {
  const [imageError, setImageError] = useState(false)
  const showPhoto = meal.has_image !== false && !imageError

  return (
    <div className="relative size-12 flex-none overflow-hidden rounded-lg bg-muted">
      {showPhoto ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={photoThumbSrc(meal.source_photo_id)}
          alt={meal.dish_name}
          className="size-full object-cover"
          onError={() => setImageError(true)}
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
  const searchAnchorRef = useRef<HTMLDivElement>(null)
  const onFocusScroll = useFocusScrollIntoView()
  const keyboardOpen = useKeyboardOpen()
  const listMaxHeight = useClampedHeightBelow(searchAnchorRef, {
    enabled: open && keyboardOpen,
  })
  const q = query.trim().toLowerCase()
  const filtered = q ? meals.filter((m) => m.dish_name.toLowerCase().includes(q)) : meals

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="gap-3">
        <DialogHeader>
          <DialogTitle>Log again</DialogTitle>
          <DialogDescription>
            Pick a meal you&apos;ve logged before to re-log it for this day — no photo, no re-analysis.
          </DialogDescription>
        </DialogHeader>

        <div ref={searchAnchorRef} className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            autoFocus
            value={query}
            onFocus={onFocusScroll}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search meals…"
            className="pl-9"
          />
        </div>

        <div
          className="-mx-1 space-y-1.5 overflow-y-auto px-1"
          style={{ maxHeight: listMaxHeight != null ? listMaxHeight : '55vh' }}
        >
          {filtered.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No meals match &ldquo;{query}&rdquo;.
            </p>
          ) : (
            filtered.map((meal) => (
              <button
                key={meal.source_photo_id}
                type="button"
                onClick={() => onClone(meal)}
                disabled={cloningId !== null}
                className="flex w-full items-center gap-3 rounded-xl border border-border bg-background p-2 text-left transition-colors hover:border-primary disabled:opacity-60"
                aria-label={`Log ${meal.dish_name} again`}
              >
                <RecentMealThumb meal={meal} loading={cloningId === meal.source_photo_id} />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{meal.dish_name}</div>
                  <div className="mt-0.5 flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">
                      {meal.times_logged > 1 ? `Logged ${meal.times_logged}×` : 'Logged once'}
                    </span>
                    <DietFlagPills flags={meal.diet_flags} />
                  </div>
                </div>
              </button>
            ))
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

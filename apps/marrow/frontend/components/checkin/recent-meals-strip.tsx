'use client'

import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { useCloneMeal, useRecentMeals } from '@/lib/api/hooks'
import { handleMutationError } from '@f0rge/ui/api'
import type { RecentMeal } from '@/lib/api/types'
import { DietFlagPills } from './diet-flag-pills'
import { MealIconThumb, photoThumbSrc } from './meal-icon-thumb'
import { LogAgainSheet } from './log-again-sheet'

// Relative "when last eaten" label. Builds both dates at local midnight (from
// YYYY-MM-DD parts, not Date-parsing the string) to avoid UTC-offset drift.
function lastLoggedLabel(dateStr: string): string {
  const [y, m, d] = dateStr.split('-').map(Number)
  const then = new Date(y, m - 1, d)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const diffDays = Math.round((today.getTime() - then.getTime()) / 86_400_000)
  if (diffDays <= 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return then.toLocaleDateString('en-GB', { weekday: 'short' })
  return then.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}

function RecentMealChip({
  meal,
  loading,
  onClick,
}: {
  meal: RecentMeal
  loading: boolean
  onClick: () => void
}) {
  const [imageError, setImageError] = useState(false)
  const showPhoto = meal.has_image !== false && !imageError

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={loading}
      aria-label={`Log ${meal.dish_name} again`}
      className="flex w-28 flex-none flex-col gap-1.5 rounded-xl border border-border bg-background p-2 text-left transition-colors hover:border-primary disabled:opacity-60"
    >
      <div className="relative aspect-square w-full overflow-hidden rounded-lg bg-muted">
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
      <div className="line-clamp-2 text-xs font-medium leading-tight">{meal.dish_name}</div>
      <div className="text-[10px] text-muted-foreground">
        {lastLoggedLabel(meal.last_logged)}
        {meal.times_logged > 1 ? ` · ×${meal.times_logged}` : ''}
      </div>
      <DietFlagPills flags={meal.diet_flags} />
    </button>
  )
}

export function RecentMealsStrip({ date }: { date: string }) {
  const { data: meals = [], isLoading } = useRecentMeals(24)
  const cloneMeal = useCloneMeal()
  const [sheetOpen, setSheetOpen] = useState(false)
  const [cloningId, setCloningId] = useState<number | null>(null)

  const handleClone = async (meal: RecentMeal) => {
    setCloningId(meal.source_photo_id)
    try {
      await cloneMeal.mutateAsync({ date, sourcePhotoId: meal.source_photo_id })
      toast.success(`Logged again: ${meal.dish_name}`)
      setSheetOpen(false)
    } catch (err) {
      handleMutationError(err, 'Failed to log meal again')
    } finally {
      setCloningId(null)
    }
  }

  // Nothing to re-log yet (no confirmed meals in history) — render nothing.
  if (isLoading || meals.length === 0) return null

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold">Log again</span>
        {meals.length > 8 && (
          <button
            type="button"
            onClick={() => setSheetOpen(true)}
            className="text-xs font-medium text-primary hover:underline"
          >
            Search all
          </button>
        )}
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {meals.slice(0, 8).map((meal) => (
          <RecentMealChip
            key={meal.source_photo_id}
            meal={meal}
            loading={cloningId === meal.source_photo_id}
            onClick={() => handleClone(meal)}
          />
        ))}
      </div>
      <LogAgainSheet
        open={sheetOpen}
        onOpenChange={setSheetOpen}
        meals={meals}
        cloningId={cloningId}
        onClone={handleClone}
      />
    </div>
  )
}

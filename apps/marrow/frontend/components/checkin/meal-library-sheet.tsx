'use client'

import { useEffect, useState } from 'react'
import { ArrowLeft, Loader2, Search } from 'lucide-react'
import { toast } from 'sonner'
import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  Input,
} from '@f0rge/ui'
import { handleMutationError } from '@f0rge/ui/api'
import { useLogFromLibrary, usePlatformMeals } from '@/lib/api/hooks'
import type { PlatformMeal } from '@/lib/api/types'
import { DietFlagPills } from './diet-flag-pills'
import { MealIconThumb } from './meal-icon-thumb'
import { MealTimeChips } from './meal-time-chips'

interface MealLibrarySheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  date: string
  ensureEntryExists: () => Promise<void>
  onEntryEnsured?: () => void
}

function ingredientPreview(ingredients: string[]): string {
  if (ingredients.length === 0) return ''
  const first = ingredients.slice(0, 3).join(' · ')
  const rest = ingredients.length - 3
  return rest > 0 ? `${first} +${rest}` : first
}

export function MealLibrarySheet({
  open,
  onOpenChange,
  date,
  ensureEntryExists,
  onEntryEnsured,
}: MealLibrarySheetProps) {
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [selected, setSelected] = useState<PlatformMeal | null>(null)
  const [mealTime, setMealTime] = useState<Date | null>(new Date())

  useEffect(() => {
    const handle = window.setTimeout(() => setDebouncedQuery(query.trim()), 250)
    return () => window.clearTimeout(handle)
  }, [query])

  const mealsQuery = usePlatformMeals({
    q: debouncedQuery || undefined,
    enabled: open,
  })
  const meals = mealsQuery.data ?? []
  const isLoading = mealsQuery.isPending || (mealsQuery.isFetching && meals.length === 0)
  const logFromLibrary = useLogFromLibrary()

  const handleOpenChange = (next: boolean) => {
    if (!next) {
      setSelected(null)
      setQuery('')
      setDebouncedQuery('')
      setMealTime(new Date())
    }
    onOpenChange(next)
  }

  const handleLog = async () => {
    if (!selected) return
    try {
      await ensureEntryExists()
      onEntryEnsured?.()
      await logFromLibrary.mutateAsync({
        date,
        platformMealId: selected.id,
        mealTime: mealTime?.toISOString(),
      })
      toast.success(`Logged: ${selected.name}`)
      handleOpenChange(false)
    } catch (err) {
      handleMutationError(err, 'Failed to log meal')
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="gap-3">
        {selected ? (
          <>
            <DialogHeader>
              <DialogTitle>Log meal</DialogTitle>
              <DialogDescription>
                Ingredients and diet flags come from the library recipe.
              </DialogDescription>
            </DialogHeader>

            <div className="flex items-start gap-3">
              <MealIconThumb iconKey={selected.icon_key} size="lg" className="shrink-0 rounded-xl" />
              <div className="min-w-0 flex-1">
                <div className="text-base font-semibold">{selected.name}</div>
                <div className="mt-1.5">
                  <DietFlagPills flags={selected.diet_flags} />
                </div>
                {selected.ingredients.length > 0 && (
                  <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                    {selected.ingredients.join(' · ')}
                  </p>
                )}
              </div>
            </div>

            <div>
              <p className="mb-1.5 text-xs font-medium text-muted-foreground">Meal time</p>
              <MealTimeChips value={mealTime} onChange={setMealTime} />
            </div>

            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                className="min-h-[44px] flex-1"
                onClick={() => setSelected(null)}
                disabled={logFromLibrary.isPending}
              >
                <ArrowLeft className="mr-1.5 size-4" />
                Back
              </Button>
              <Button
                type="button"
                className="min-h-[44px] flex-1"
                onClick={() => void handleLog()}
                disabled={logFromLibrary.isPending}
              >
                {logFromLibrary.isPending ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  'Log meal'
                )}
              </Button>
            </div>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>Meal library</DialogTitle>
              <DialogDescription>
                Platform dishes built from the ingredient catalog. Tap to log — no photo.
              </DialogDescription>
            </DialogHeader>

            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search meals…"
                className="pl-9"
              />
            </div>

            <div className="-mx-1 max-h-[50vh] overflow-y-auto px-1">
              {mealsQuery.isError ? (
                <div className="flex flex-col items-center gap-3 py-6 text-center">
                  <p className="text-sm text-muted-foreground">
                    Could not load the meal library. Check your connection and try again.
                  </p>
                  <Button
                    type="button"
                    variant="outline"
                    className="min-h-[44px]"
                    onClick={() => {
                      void mealsQuery.refetch()
                    }}
                  >
                    Retry
                  </Button>
                </div>
              ) : isLoading ? (
                <div className="flex justify-center py-8 text-muted-foreground">
                  <Loader2 className="size-5 animate-spin" />
                </div>
              ) : meals.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">
                  No library meals match. Try Take Photo instead.
                </p>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  {meals.map((meal) => (
                    <button
                      key={meal.id}
                      type="button"
                      onClick={() => {
                        setSelected(meal)
                        setMealTime(new Date())
                      }}
                      className="flex min-h-[44px] flex-col gap-2 rounded-xl border border-border bg-background p-2.5 text-left transition-colors hover:border-primary"
                      aria-label={`Log ${meal.name}`}
                    >
                      <MealIconThumb iconKey={meal.icon_key} size="md" className="aspect-square w-full rounded-lg" />
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium">{meal.name}</div>
                        <p className="mt-0.5 line-clamp-2 text-[10px] leading-tight text-muted-foreground">
                          {ingredientPreview(meal.ingredients)}
                        </p>
                        <div className="mt-1">
                          <DietFlagPills flags={meal.diet_flags} />
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}

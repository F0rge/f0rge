'use client'

import { EyeOff, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button, FetchError } from '@f0rge/ui'
import { handleMutationError } from '@f0rge/ui/api'
import { mealDay } from '@/components/profile/meal-grids'
import { MealIconThumb, photoHasImage, photoThumbSrc } from '@/components/checkin/meal-icon-thumb'
import { useUpdatePhotoVisibility } from '@/lib/api/hooks/entries'
import { usePhotos } from '@/lib/api/hooks/photos'
import { SettingsCard } from './settings-card'

export function HiddenMealsSection() {
  const photos = usePhotos('all', { visibility: 'hidden' })
  const updateVisibility = useUpdatePhotoVisibility()

  const unhide = async (photoId: number) => {
    try {
      await updateVisibility.mutateAsync({ photoId, hidden: false })
      toast.success('Meal restored to your profile')
    } catch (err) {
      handleMutationError(err, 'Could not unhide meal')
    }
  }

  const items = photos.data ?? []

  return (
    <SettingsCard icon={EyeOff} iconClassName="text-muted-foreground" title="Hidden meals">
      <p className="text-sm text-muted-foreground">
        Meals you removed from your profile grids. They stay visible in your check-ins.
      </p>
      {photos.isLoading ? (
        <div className="flex items-center justify-center py-4 text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
        </div>
      ) : photos.isError ? (
        <FetchError message="Failed to load hidden meals." onRetry={() => photos.refetch()} />
      ) : items.length === 0 ? (
        <p className="text-sm text-muted-foreground">No hidden meals.</p>
      ) : (
        <ul className="divide-y divide-border">
          {items.map((photo) => {
            // `||` on purpose: a cleared label is '' and must fall through.
            const name = photo.label || photo.dish_name || 'Meal'
            const when = mealDay(photo.meal_time ?? photo.created_at)
            return (
              <li key={photo.id} className="flex items-center gap-3 py-2.5">
                {photoHasImage(photo) ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={photoThumbSrc(photo.id)}
                    alt={name}
                    className="size-12 shrink-0 rounded-lg bg-muted object-cover ring-1 ring-foreground/10"
                  />
                ) : (
                  <MealIconThumb
                    iconKey={photo.icon_key ?? 'bowl'}
                    size="md"
                    className="size-12 shrink-0 rounded-lg"
                  />
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{name}</p>
                  {when && <p className="text-xs text-muted-foreground">{when}</p>}
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void unhide(photo.id)}
                  disabled={updateVisibility.isPending}
                >
                  Unhide
                </Button>
              </li>
            )
          })}
        </ul>
      )}
    </SettingsCard>
  )
}

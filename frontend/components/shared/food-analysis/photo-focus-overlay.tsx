'use client'

import { Dialog, DialogContent } from '@/components/ui/dialog'
import { usePhotoAnalysis } from '@/lib/api/hooks'
import { PhotoAnalysis } from './photo-analysis'
import type { Photo } from '@/lib/api/types'

interface PhotoFocusOverlayProps {
  /** ID of the photo currently in focus. `null` means the overlay is closed. */
  photoId: number | null
  /** All photos for the entry, used for the meal-tab switcher when there are ≥2. */
  photos: Photo[]
  /** Whether the underlying form is in edit mode. Mirrors `PhotoAnalysis` mode. */
  mode?: 'view' | 'edit'
  /** Called when the user closes the overlay (X, Done, Esc, or backdrop). */
  onClose: () => void
  /** Called when the user switches to another photo via the tab row. */
  onSelectPhoto: (id: number) => void
}

function formatMealTime(iso: string | null): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}

/**
 * Full-screen-friendly overlay for editing a single photo's ingredients with
 * comfortable spacing and large tap targets. Wraps the existing
 * `<PhotoAnalysis>` component without modifying it — just gives it room to
 * breathe. See issue #76 / mockups/v2-cards.html for the visual target.
 */
export function PhotoFocusOverlay({
  photoId,
  photos,
  mode = 'edit',
  onClose,
  onSelectPhoto,
}: PhotoFocusOverlayProps) {
  const open = photoId !== null
  const { data: analysis } = usePhotoAnalysis(photoId)

  const dishName = analysis?.dish_name ?? null
  const confidence =
    analysis?.dish_confidence != null
      ? Math.round(analysis.dish_confidence * 100)
      : null

  const currentPhoto = photoId !== null ? photos.find((p) => p.id === photoId) ?? null : null
  const mealTime = formatMealTime(currentPhoto?.meal_time ?? null)

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose()
      }}
    >
      <DialogContent
        showCloseButton={false}
        className="grid max-h-[92vh] w-full max-w-[calc(100%-1rem)] grid-rows-[auto_auto_1fr] gap-0 overflow-hidden p-0 sm:max-w-2xl"
      >
        {/* Header */}
        <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold leading-tight">
              {dishName || 'Photo'}
            </div>
            <div className="mt-0.5 truncate text-xs text-muted-foreground">
              {[mealTime, confidence != null ? `${confidence}% confident` : null]
                .filter(Boolean)
                .join(' · ') || 'Tap an ingredient to edit'}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 rounded-lg bg-foreground px-3 py-1.5 text-xs font-semibold text-background hover:bg-foreground/90"
            aria-label="Done editing"
          >
            Done
          </button>
        </div>

        {/* Hero image + meal tabs */}
        <div className="relative">
          {photoId !== null && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={`/api/v1/photos/${photoId}/file`}
              alt={currentPhoto?.label || dishName || 'Meal photo'}
              className="aspect-[4/3] w-full object-cover"
            />
          )}

          {photos.length > 1 && (
            <div className="absolute inset-x-0 bottom-2 flex justify-center">
              <div className="flex items-center gap-1 rounded-full border border-border bg-background/95 p-1 shadow-sm backdrop-blur">
                {photos.map((p, i) => {
                  const isActive = p.id === photoId
                  return (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => onSelectPhoto(p.id)}
                      aria-label={`Switch to photo ${i + 1}`}
                      aria-current={isActive ? 'true' : undefined}
                      className={
                        isActive
                          ? 'size-7 rounded-full bg-foreground text-xs font-semibold text-background'
                          : 'size-7 rounded-full text-xs text-muted-foreground hover:bg-muted'
                      }
                    >
                      {i + 1}
                    </button>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        {/* Body: existing PhotoAnalysis, reused unchanged. The surrounding wrapper
            gives it the breathing room the inline placement lacks. */}
        <div className="overflow-y-auto px-4 pb-4 pt-2">
          {photoId !== null && (
            <PhotoAnalysis
              key={photoId}
              photoId={photoId}
              mode={mode}
              hideConfirmButton={false}
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}

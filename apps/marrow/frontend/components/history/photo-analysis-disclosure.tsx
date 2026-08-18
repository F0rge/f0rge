'use client'

import { useState } from 'react'
import { ChevronDown, Pencil, Check } from 'lucide-react'
import { MealIconThumb, photoHasImage, photoThumbSrc } from '@/components/checkin/meal-icon-thumb'
import { usePhotoAnalysis } from '@/lib/api/hooks'
import { PhotoAnalysis } from '@/components/shared/food-analysis'
import type { Photo } from '@/lib/api/types'

interface PhotoAnalysisDisclosureProps {
  photoId: number
  photoLabel?: string | null
  photo?: Pick<Photo, 'has_image' | 'icon_key' | 'filename'>
}

function IngredientTeaser({ photoId }: { photoId: number }) {
  const { data: analysis } = usePhotoAnalysis(photoId)
  if (!analysis || analysis.status === 'pending' || analysis.status === 'analyzing') return null

  const visible = analysis.ingredients.filter((i) => i.visible)
  if (visible.length === 0) return null

  const first3 = visible.slice(0, 3).map((i) => i.name)
  const rest = visible.length - 3
  const teaser = first3.join(' · ') + (rest > 0 ? ` +${rest}` : '')

  return (
    <span className="text-[11px] text-muted-foreground">{teaser}</span>
  )
}

function SummaryContent({
  photoId,
  photoLabel,
  photo,
}: {
  photoId: number
  photoLabel?: string | null
  photo?: Pick<Photo, 'has_image' | 'icon_key' | 'filename'>
}) {
  const { data: analysis } = usePhotoAnalysis(photoId)

  const dishName = photoLabel?.trim() || analysis?.dish_name || `Photo ${photoId}`
  const confidence =
    analysis?.dish_confidence !== null && analysis?.dish_confidence !== undefined
      ? Math.round(analysis.dish_confidence * 100)
      : null
  const isConfirmed = analysis?.status === 'confirmed'
  const showImage = photo ? photoHasImage(photo) : true

  return (
    <>
      {showImage ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={photoThumbSrc(photoId)}
          alt={dishName}
          className="size-9 shrink-0 rounded object-cover"
        />
      ) : (
        <MealIconThumb
          iconKey={photo?.icon_key ?? 'bowl'}
          size="sm"
          className="size-9 shrink-0 rounded"
        />
      )}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span className="truncate text-sm font-semibold">{dishName}</span>
          {confidence !== null && (
            <span className="shrink-0 text-xs text-muted-foreground">({confidence}%)</span>
          )}
          {isConfirmed && (
            <Check className="ml-1 size-3.5 shrink-0 text-green-600" />
          )}
        </div>
        <div className="mt-0.5">
          <IngredientTeaser photoId={photoId} />
        </div>
      </div>
    </>
  )
}

export function PhotoAnalysisDisclosure({ photoId, photoLabel, photo }: PhotoAnalysisDisclosureProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [isEditing, setIsEditing] = useState(false)

  const bodyId = `photo-analysis-body-${photoId}`

  const handleToggle = () => {
    setIsExpanded((prev) => {
      if (prev) setIsEditing(false)
      return !prev
    })
  }

  const handleDoneEditing = () => {
    setIsEditing(false)
  }

  return (
    <div className="rounded-lg border border-border bg-card">
      <button
        type="button"
        onClick={handleToggle}
        aria-expanded={isExpanded}
        aria-controls={bodyId}
        className="flex w-full items-center gap-2 px-2.5 py-2 text-left"
      >
        <SummaryContent photoId={photoId} photoLabel={photoLabel} photo={photo} />
        <ChevronDown
          className={`size-4 shrink-0 text-muted-foreground transition-transform duration-150 ${
            isExpanded ? 'rotate-180' : ''
          }`}
        />
      </button>

      {isExpanded && (
        <div id={bodyId} className="border-t border-border px-2.5 pb-2.5 pt-2">
          <PhotoAnalysis photoId={photoId} mode={isEditing ? 'edit' : 'view'} />
          <div className="mt-2 flex justify-end">
            {isEditing ? (
              <button
                type="button"
                onClick={handleDoneEditing}
                className="flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs font-medium text-foreground transition-colors hover:bg-muted"
              >
                Done editing
              </button>
            ) : (
              <button
                type="button"
                onClick={() => setIsEditing(true)}
                className="flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-xs font-medium text-foreground transition-colors hover:bg-muted"
              >
                <Pencil className="size-3" />
                Edit
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

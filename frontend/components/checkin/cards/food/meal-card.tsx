'use client'

import { Loader2, X } from 'lucide-react'
import { buildAggregateBadges } from '@/components/shared/food-analysis/dietary-badges'
import type { Photo } from '@/lib/api/types'
import { usePhotoAnalysis } from '@/lib/api/hooks'

export interface MealCardProps {
  photo: Photo
  onOpen: (photoId: number) => void
  onDelete: (photoId: number) => void
  deleting: boolean
}

export function MealCard({ photo, onOpen, onDelete, deleting }: MealCardProps) {
  const { data: analysis, isLoading } = usePhotoAnalysis(photo.id)

  const isAnalyzing = isLoading || analysis?.status === 'pending' || analysis?.status === 'analyzing'
  const title = photo.label?.trim() || analysis?.dish_name || 'Untitled meal'
  const confidence =
    analysis?.dish_confidence != null ? Math.round(analysis.dish_confidence * 100) : null
  const badges = analysis
    ? buildAggregateBadges(analysis.ingredients, {
        glutenFreeConfirmed: analysis.gluten_free_confirmed,
        lactoseFreeConfirmed: analysis.lactose_free_confirmed,
      })
    : []

  return (
    <div className="group relative overflow-hidden rounded-xl border border-border">
      <div
        role="button"
        tabIndex={0}
        onClick={() => onOpen(photo.id)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            onOpen(photo.id)
          }
        }}
        aria-label={`Review and edit ${title}`}
        className="cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={`/api/v1/photos/${photo.id}/file`}
          alt={title}
          className="aspect-square w-full object-cover"
        />
        <div className="p-2.5">
          {isAnalyzing ? (
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Loader2 className="size-3.5 animate-spin" />
              Analyzing...
            </div>
          ) : (
            <>
              <div className="flex items-center gap-1.5">
                <span className="truncate text-sm font-semibold text-foreground">{title}</span>
                {confidence !== null && (
                  <span className="shrink-0 text-xs text-muted-foreground">({confidence}%)</span>
                )}
              </div>
              {badges.length > 0 && (
                <span className="mt-1 inline-flex flex-wrap gap-0.5">
                  {badges.map((b, i) => (
                    <span
                      key={i}
                      className={`inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium leading-none ${b.className}`}
                    >
                      {b.label}
                    </span>
                  ))}
                </span>
              )}
            </>
          )}
        </div>
      </div>
      <button
        type="button"
        disabled={deleting}
        onClick={(e) => {
          e.stopPropagation()
          onDelete(photo.id)
        }}
        className="absolute right-1.5 top-1.5 flex size-7 items-center justify-center rounded-full bg-black/60 text-white transition-colors hover:bg-black/80"
        aria-label="Delete photo"
      >
        <X className="size-4" />
      </button>
    </div>
  )
}

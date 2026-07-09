'use client'

import { Camera, X, Loader2 } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { PhotoCapture } from '@/components/checkin/photo-capture'
import { RecentMealsStrip } from '@/components/checkin/recent-meals-strip'
import { buildAggregateBadges } from '@/components/shared/food-analysis/dietary-badges'
import type { Entry, PhotoSignal, DietTagCatalogItem, Photo } from '@/lib/api/types'
import { useDeletePhoto, useDietTagCatalog, usePhotoAnalysis } from '@/lib/api/hooks'
import { handleMutationError } from '@/lib/api/client'
import { useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { useState } from 'react'
import { TierPill } from '@/components/customize/tier-pill'

// ---------------------------------------------------------------------------
// DietRiskSection — data-entry section for diet risk flags.
// ---------------------------------------------------------------------------

function getFlagScore(flag: string, signal: PhotoSignal): number {
  switch (flag) {
    case 'high-histamine': return signal.scores.histamine_load
    case 'high-fodmap': return signal.scores.fodmap_count
    case 'gluten': return signal.scores.gluten_count
    case 'dairy': return signal.scores.dairy_count
    default: return 0
  }
}

function buildSourceLine(signal: PhotoSignal, catalog: DietTagCatalogItem[]): string {
  return signal.flags
    .map((flag) => {
      const ingredients = signal.sources[flag]
      if (!ingredients || ingredients.length === 0) return null
      const catalogItem = catalog.find((o) => o.key === flag)
      return `${catalogItem?.label ?? flag}: ${ingredients.join(', ')}`
    })
    .filter(Boolean)
    .join(' · ')
}

interface LockedChipProps {
  flag: string
  label: string
  score: number
  title: string
}

function LockedChip({ flag, label, score, title }: LockedChipProps) {
  return (
    <span
      key={flag}
      title={title}
      className="inline-flex items-center gap-2 min-h-[48px] rounded-xl border border-primary bg-foreground text-primary-foreground px-3 py-2.5 text-sm font-medium cursor-not-allowed shadow-sm"
    >
      <span className="inline-flex size-[18px] shrink-0 items-center justify-center rounded-full bg-white/20">
        <Camera className="size-2.5" />
      </span>
      {label}
      <span className="inline-flex min-w-[22px] h-[22px] items-center justify-center rounded-full px-1.5 text-xs font-bold bg-white/20 text-primary-foreground tabular-nums">
        {score}
      </span>
    </span>
  )
}

interface PhotoDerivedRowProps {
  signal: PhotoSignal
  photoCount: number
  catalog: DietTagCatalogItem[]
}

function PhotoDerivedRow({ signal, photoCount, catalog }: PhotoDerivedRowProps) {
  const sourceLine = buildSourceLine(signal, catalog)
  const ingredientCount = Object.values(signal.sources).reduce((sum, arr) => sum + arr.length, 0)

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Camera className="size-3.5" />
          From photos (locked)
        </div>
        <span className="text-xs text-muted-foreground">
          {photoCount} {photoCount === 1 ? 'photo' : 'photos'} &middot; {ingredientCount} ingredients
        </span>
      </div>
      {signal.flags.length > 0 ? (
        <>
          <div className="flex flex-wrap gap-2">
            {signal.flags.map((flag) => {
              const catalogItem = catalog.find((o) => o.key === flag)
              const score = getFlagScore(flag, signal)
              const sources = signal.sources[flag] ?? []
              const flagLabel = catalogItem?.label ?? flag
              const scoreDescription = flag === 'high-histamine'
                ? `Σ histamine_score = ${score}`
                : `${score} ingredient${score !== 1 ? 's' : ''}`
              return (
                <LockedChip
                  key={flag}
                  flag={flag}
                  label={flagLabel}
                  score={score}
                  title={`${scoreDescription}${sources.length > 0 ? `: ${sources.join(', ')}` : ''}`}
                />
              )
            })}
          </div>
          {sourceLine && (
            <p className="text-[0.7rem] leading-[1.4] text-muted-foreground">{sourceLine}</p>
          )}
        </>
      ) : (
        <p className="text-xs text-muted-foreground">Photos confirmed — no risk flags detected.</p>
      )}
    </div>
  )
}

interface DietRiskSectionProps {
  existingEntry?: Entry | null
  existingPhotos: Entry['photos']
  dietRisk: string
  onToggle: (key: string) => void
  catalog: DietTagCatalogItem[]
  catalogLoading: boolean
}

function DietRiskSection({ existingEntry, existingPhotos, dietRisk, onToggle, catalog, catalogLoading }: DietRiskSectionProps) {
  const hasPhotos = existingPhotos.length > 0
  const signal: PhotoSignal = existingEntry?.photo_signal ?? {
    flags: [],
    scores: { histamine_load: 0, fodmap_count: 0, gluten_count: 0, dairy_count: 0 },
    sources: {},
  }
  const signalIsLive = signal.flags.length > 0 || signal.scores.histamine_load > 0
  const manualOptions = catalog.filter((o) => !signal.flags.includes(o.key))
  const selectedFlags = dietRisk ? dietRisk.split(',').filter(Boolean) : []

  return (
    <div className="space-y-3">
      <label className="text-sm font-semibold">Diet risk</label>
      {hasPhotos ? (
        signalIsLive ? (
          <PhotoDerivedRow signal={signal} photoCount={existingPhotos.length} catalog={catalog} />
        ) : (
          <div className="rounded-xl border border-dashed border-border bg-background p-3">
            <div className="flex items-center gap-1.5 text-muted-foreground">
              <Camera className="size-3.5" />
              <span className="text-xs">Photos still analyzing — flags will update once confirmed.</span>
            </div>
          </div>
        )
      ) : (
        <div className="rounded-xl border border-dashed border-border bg-background p-3">
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Camera className="size-3.5" />
            <span className="text-xs">No food photos for today — anything below is fully manual.</span>
          </div>
        </div>
      )}
      {signalIsLive && <div className="h-px bg-border" />}
      <div className="space-y-2">
        <p className="text-xs text-muted-foreground">
          {hasPhotos ? 'Add anything else you ate or drank' : 'Add anything you ate or drank'}
        </p>
        {catalogLoading ? (
          <div className="grid grid-cols-2 gap-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-12 animate-pulse rounded-xl bg-muted" />
            ))}
          </div>
        ) : manualOptions.length > 0 && (
          <div className="grid grid-cols-2 gap-2">
            {manualOptions.map((opt) => {
              const selected = selectedFlags.includes(opt.key)
              return (
                <button
                  key={opt.key}
                  type="button"
                  onClick={() => onToggle(opt.key)}
                  className={[
                    'min-h-[48px] rounded-xl border px-2 py-2.5 text-sm font-medium transition-all',
                    selected
                      ? 'border-primary bg-primary text-primary-foreground shadow-sm'
                      : 'border-border bg-background text-muted-foreground',
                  ].join(' ')}
                >
                  {opt.label}
                </button>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// MealCard — one media card per meal: photo + title/confidence/badges in a
// single bordered container. Whole card opens PhotoFocusOverlay; the delete
// button is a sibling so it can stop propagation instead of nesting inside
// the tap target (nested <button>s are invalid HTML).
// ---------------------------------------------------------------------------

interface MealCardProps {
  photo: Photo
  onOpen: (photoId: number) => void
  onDelete: (photoId: number) => void
  deleting: boolean
}

function MealCard({ photo, onOpen, onDelete, deleting }: MealCardProps) {
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

// ---------------------------------------------------------------------------
// FoodCard
// ---------------------------------------------------------------------------

interface FoodCardProps {
  date: string
  existingEntry?: Entry | null
  existingPhotos: Entry['photos']
  dietRisk: string
  onDietToggle: (id: string) => void
  onPhotosChange: (photos: Entry['photos']) => void
  ensureEntryExists: () => Promise<void>
  onEntryEnsured: () => void
  onOpenPhotoFocus: (photoId: number) => void
}

export function FoodCard({
  date,
  existingEntry,
  existingPhotos,
  dietRisk,
  onDietToggle,
  onPhotosChange,
  ensureEntryExists,
  onEntryEnsured,
  onOpenPhotoFocus,
}: FoodCardProps) {
  const deletePhotoMutation = useDeletePhoto()
  const queryClient = useQueryClient()
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const { data: dietCatalog = [], isLoading: dietCatalogLoading } = useDietTagCatalog(false)

  const handleDeletePhoto = async (photoId: number) => {
    setDeletingId(photoId)
    try {
      await deletePhotoMutation.mutateAsync(photoId)
      onPhotosChange(existingPhotos.filter((p) => p.id !== photoId))
      queryClient.invalidateQueries({ queryKey: ['entry', date] })
      toast.success('Photo deleted')
    } catch (err) {
      handleMutationError(err, 'Failed to delete photo')
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
          <Camera className="size-4" />
          Food &amp; drinks
          <TierPill tier="core" />
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <DietRiskSection
          existingEntry={existingEntry}
          existingPhotos={existingPhotos}
          dietRisk={dietRisk}
          onToggle={onDietToggle}
          catalog={dietCatalog}
          catalogLoading={dietCatalogLoading}
        />

        {existingPhotos.length > 0 && (
          <div className="space-y-3">
            <label className="text-sm font-semibold">Uploaded photos</label>
            <div className="grid grid-cols-2 gap-3">
              {existingPhotos.map((photo) => (
                <MealCard
                  key={photo.id}
                  photo={photo}
                  onOpen={onOpenPhotoFocus}
                  onDelete={handleDeletePhoto}
                  deleting={deletingId === photo.id}
                />
              ))}
            </div>
          </div>
        )}

        <RecentMealsStrip date={date} />

        <PhotoCapture
          date={date}
          ensureEntryExists={ensureEntryExists}
          onEntryEnsured={onEntryEnsured}
        />
      </CardContent>
    </Card>
  )
}

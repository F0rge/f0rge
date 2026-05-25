'use client'

import { Camera, Maximize2, X } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { PhotoCapture } from '@/components/checkin/photo-capture'
import { PhotoAnalysis } from '@/components/shared/food-analysis'
import type { Entry, PhotoSignal, DietTagCatalogItem } from '@/lib/api/types'
import { useDeletePhoto, useDietTagCatalog } from '@/lib/api/hooks'
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
}

function DietRiskSection({ existingEntry, existingPhotos, dietRisk, onToggle, catalog }: DietRiskSectionProps) {
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
        {manualOptions.length > 0 && (
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
  onOpenPhotoFocus?: (photoId: number) => void
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
  const { data: dietCatalog = [] } = useDietTagCatalog(false)

  const handleDeletePhoto = async (photoId: number) => {
    setDeletingId(photoId)
    try {
      await deletePhotoMutation.mutateAsync(photoId)
      onPhotosChange(existingPhotos.filter((p) => p.id !== photoId))
      queryClient.invalidateQueries({ queryKey: ['entry', date] })
      toast.success('Photo deleted')
    } catch {
      toast.error('Failed to delete photo')
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
        />

        {existingPhotos.length > 0 && (
          <div className="space-y-3">
            <label className="text-sm font-semibold">Uploaded photos</label>
            <div className="grid grid-cols-2 gap-3">
              {existingPhotos.map((photo) => (
                <div key={photo.id}>
                  <div className="group relative rounded-xl border border-border overflow-hidden">
                    {onOpenPhotoFocus ? (
                      <button
                        type="button"
                        onClick={() => onOpenPhotoFocus(photo.id)}
                        className="block w-full focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        aria-label={`Open focus editor for ${photo.label || 'photo'}`}
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={`/api/v1/photos/${photo.id}/file`}
                          alt={photo.label || 'Photo'}
                          className="aspect-square w-full object-cover"
                        />
                      </button>
                    ) : (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        src={`/api/v1/photos/${photo.id}/file`}
                        alt={photo.label || 'Photo'}
                        className="aspect-square w-full object-cover"
                      />
                    )}
                    {photo.label && (
                      <div className="px-2 py-1.5 text-xs text-muted-foreground truncate">
                        {photo.label}
                      </div>
                    )}
                    {onOpenPhotoFocus && (
                      <button
                        type="button"
                        onClick={() => onOpenPhotoFocus(photo.id)}
                        className="absolute left-1.5 top-1.5 flex size-7 items-center justify-center rounded-full bg-black/60 text-white transition-colors hover:bg-black/80 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        aria-label={`Open focus editor for ${photo.label || 'photo'}`}
                      >
                        <Maximize2 className="size-3.5" />
                      </button>
                    )}
                    <button
                      type="button"
                      disabled={deletingId === photo.id}
                      onClick={() => handleDeletePhoto(photo.id)}
                      className="absolute right-1.5 top-1.5 flex size-7 items-center justify-center rounded-full bg-black/60 text-white transition-colors hover:bg-black/80"
                      aria-label="Delete photo"
                    >
                      <X className="size-4" />
                    </button>
                  </div>
                  <PhotoAnalysis photoId={photo.id} />
                </div>
              ))}
            </div>
          </div>
        )}

        <PhotoCapture
          date={date}
          ensureEntryExists={ensureEntryExists}
          onEntryEnsured={onEntryEnsured}
        />
      </CardContent>
    </Card>
  )
}

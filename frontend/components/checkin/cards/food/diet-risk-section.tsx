'use client'

import { useQueries } from '@tanstack/react-query'
import { Camera } from 'lucide-react'
import { apiGet, ApiError } from '@/lib/api/client'
import type { Entry, PhotoSignal, DietTagCatalogItem, PhotoAnalysis } from '@/lib/api/types'

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

export interface DietRiskSectionProps {
  existingEntry?: Entry | null
  existingPhotos: Entry['photos']
  dietRisk: string
  onToggle: (key: string) => void
  catalog: DietTagCatalogItem[]
  catalogLoading: boolean
}

export function DietRiskSection({
  existingEntry,
  existingPhotos,
  dietRisk,
  onToggle,
  catalog,
  catalogLoading,
}: DietRiskSectionProps) {
  const hasPhotos = existingPhotos.length > 0
  const analysisQueries = useQueries({
    queries: existingPhotos.map((photo) => ({
      queryKey: ['photo-analysis', photo.id],
      queryFn: async (): Promise<PhotoAnalysis | null> => {
        try {
          return await apiGet(`/photos/${photo.id}/analysis`)
        } catch (err) {
          if (err instanceof ApiError && err.status === 404) {
            return null
          }
          throw err
        }
      },
      refetchInterval: (query: { state: { data?: PhotoAnalysis | null } }) => {
        const status = query.state.data?.status
        if (status === 'pending' || status === 'analyzing') {
          return 2000
        }
        return false
      },
    })),
  })
  const analyses = analysisQueries.map((query) => query.data)
  const analysesLoading = analysisQueries.some((query) => query.isLoading)
  const anyStillAnalyzing =
    analysesLoading ||
    analyses.some((analysis) => analysis?.status === 'pending' || analysis?.status === 'analyzing')
  const anyAwaitingConfirm = analyses.some(
    (analysis) => analysis?.status === 'needs_review' || analysis?.status === 'complete',
  )
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
              <span className="text-xs">
                {anyStillAnalyzing
                  ? 'Photos still analyzing — flags will update once confirmed.'
                  : anyAwaitingConfirm
                    ? 'Review photo ingredients above — diet flags will update once confirmed.'
                    : 'Photos still analyzing — flags will update once confirmed.'}
              </span>
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

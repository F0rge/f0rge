'use client'

import { useState } from 'react'
import Image from 'next/image'
import { LayoutGrid, Tag } from 'lucide-react'
import { cn, formatDisplayDate, formatLocalDate } from '@f0rge/ui'
import { usePhotos } from '@/lib/api/hooks'
import type { Photo } from '@/lib/api/types'

/**
 * `Today · 19:30` / `Yesterday` / `Tuesday` (<7 days) / `2 Jun 2026`.
 *
 * Mirrors `formatMealTime` in components/shared/food-analysis/photo-focus-overlay.tsx:
 * backend timestamps are tz-naive UTC and `new Date(iso)` reads them as local
 * wall-clock everywhere in the app — keep these semantics identical.
 */
function mealDay(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const that = new Date(d)
  that.setHours(0, 0, 0, 0)
  const diff = Math.round((today.getTime() - that.getTime()) / 86_400_000)
  if (diff === 0) {
    return `Today · ${d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}`
  }
  if (diff === 1) return 'Yesterday'
  if (diff < 7) return d.toLocaleDateString('en-GB', { weekday: 'long' })
  // formatDisplayDate parses `YYYY-MM-DD`, not a datetime — handing it the raw
  // ISO string yields "Invalid Date", so narrow to the local calendar day first.
  return formatDisplayDate(formatLocalDate(d))
}

function Grid({ photos, tagged, empty }: { photos: Photo[]; tagged?: boolean; empty: string }) {
  if (photos.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
        {empty}
      </p>
    )
  }
  return (
    <div className="grid grid-cols-3 gap-1.5">
      {photos.map((photo) => {
        // User label wins, AI dish name is the fallback; `||` (not `??`) so a
        // cleared label ('') falls through to the AI guess instead of rendering blank.
        const name = photo.label || photo.dish_name
        const when = mealDay(photo.meal_time ?? photo.created_at)
        return (
          <div
            key={photo.id}
            className="relative aspect-square overflow-hidden rounded-xl bg-muted ring-1 ring-foreground/10"
          >
            <Image
              src={`/api/v1/photos/${photo.id}/file`}
              alt={photo.label ?? 'Meal photo'}
              fill
              unoptimized
              sizes="(max-width: 672px) 33vw, 224px"
              className="object-cover"
            />
            {tagged && photo.tagged_by_handle && (
              <span className="absolute left-1.5 top-1.5 z-10 rounded-full bg-card px-1.5 text-[8.5px] font-bold leading-4 ring-1 ring-border">
                @{photo.tagged_by_handle}
              </span>
            )}
            {(name || when) && (
              <span className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/60 to-transparent px-1.5 pb-1 pt-3.5 text-left">
                {name && (
                  <span className="block truncate text-[9.5px] font-semibold text-white">{name}</span>
                )}
                {when && <span className="block truncate text-[8.5px] text-white/75">{when}</span>}
              </span>
            )}
          </div>
        )
      })}
    </div>
  )
}

export function MealGrids() {
  const [tab, setTab] = useState<'all' | 'tagged'>('all')
  const allPhotos = usePhotos('all')
  const taggedPhotos = usePhotos('tagged')

  return (
    <section className="space-y-3">
      <div className="flex border-b border-muted" role="tablist" aria-label="Meal photos">
        {(['all', 'tagged'] as const).map((key) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={cn(
              'flex flex-1 items-center justify-center gap-1.5 border-b-2 pb-2.5 pt-1 text-xs font-semibold transition-colors',
              tab === key
                ? 'border-foreground text-foreground'
                : 'border-transparent text-muted-foreground',
            )}
          >
            {key === 'all' ? (
              <LayoutGrid className="size-4" aria-hidden />
            ) : (
              <Tag className="size-4" aria-hidden />
            )}
            {key === 'all' ? 'My meals' : 'Shared with me'}
          </button>
        ))}
      </div>
      {tab === 'all' ? (
        <Grid photos={allPhotos.data ?? []} empty="No meals logged yet." />
      ) : (
        <Grid
          photos={taggedPhotos.data ?? []}
          tagged
          empty="Nothing shared with you yet — connections can tag you on meal photos."
        />
      )}
    </section>
  )
}

'use client'

import { useState } from 'react'
import Image from 'next/image'
import { LayoutGrid, Tag } from 'lucide-react'
import { cn } from '@f0rge/ui'
import { usePhotos } from '@/lib/api/hooks'
import type { Photo } from '@/lib/api/types'

function Grid({ photos, tagged, empty }: { photos: Photo[]; tagged?: boolean; empty: string }) {
  if (photos.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
        {empty}
      </p>
    )
  }
  return (
    <div className="grid grid-cols-3 gap-[3px] overflow-hidden rounded-xl">
      {photos.map((photo) => (
        <div key={photo.id} className="relative aspect-square bg-muted">
          <Image
            src={`/api/v1/photos/${photo.id}/file`}
            alt={photo.label ?? 'Meal photo'}
            fill
            unoptimized
            sizes="(max-width: 672px) 33vw, 224px"
            className="object-cover"
          />
          {tagged && photo.tagged_by_handle && (
            <span className="absolute bottom-1.5 left-1.5 rounded-full bg-background/85 px-1.5 py-0.5 text-[10px] font-semibold">
              @{photo.tagged_by_handle}
            </span>
          )}
        </div>
      ))}
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
            {key === 'all' ? 'Meals' : 'Tagged'}
          </button>
        ))}
      </div>
      {tab === 'all' ? (
        <Grid photos={allPhotos.data ?? []} empty="No meals logged yet." />
      ) : (
        <Grid
          photos={taggedPhotos.data ?? []}
          tagged
          empty="No tagged meals yet — connections can tag you on meal photos."
        />
      )}
    </section>
  )
}

'use client'

import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { useMarkerHistory } from '@/lib/api/hooks'
import type { SignalsTrendSeries } from '@/lib/api/types/signals'
import { SignalsTrendCard } from './trend-card'

const PINNED_KEY = 'labs.pinnedMarkers'

function readPinned(): string[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = localStorage.getItem(PINNED_KEY)
    return raw ? (JSON.parse(raw) as string[]) : []
  } catch {
    return []
  }
}

function usePinnedMarkers(): string[] {
  const [pinned] = useState<string[]>(readPinned)
  return pinned
}

function PinnedMarkerCard({ canonicalName }: { canonicalName: string }) {
  const { data: points, isLoading } = useMarkerHistory(canonicalName)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center rounded-xl bg-card p-3 ring-1 ring-foreground/10">
        <Loader2 className="size-4 animate-spin text-muted-foreground" />
      </div>
    )
  }

  const numericPoints = (points ?? []).filter((p) => p.value !== null)
  if (numericPoints.length === 0) return null

  const latest = numericPoints[numericPoints.length - 1]
  const trendSeries: SignalsTrendSeries = {
    key: canonicalName,
    label: canonicalName,
    category: 'lab',
    points: numericPoints.map((p) => ({
      date: p.lab_date,
      value: p.value,
      rolling_avg_7: null,
    })),
    current: latest.value,
    rolling_avg_7: null,
    delta_30d: null,
    good_direction: null,
  }

  return <SignalsTrendCard series={trendSeries} />
}

interface Props {
  series: SignalsTrendSeries[]
}

export function SignalsTrendGrid({ series }: Props) {
  const pinnedMarkers = usePinnedMarkers()

  if (series.length === 0) {
    return (
      <p className="py-4 text-sm text-muted-foreground">No trend data available.</p>
    )
  }

  return (
    <div className="space-y-4">
      {pinnedMarkers.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-medium text-muted-foreground">
            Pinned lab markers
          </p>
          <div className="grid grid-cols-2 gap-2">
            {pinnedMarkers.map((canonical) => (
              <PinnedMarkerCard key={canonical} canonicalName={canonical} />
            ))}
          </div>
        </div>
      )}
      <div className="grid grid-cols-2 gap-2">
        {series.map((s) => (
          <SignalsTrendCard key={s.key} series={s} />
        ))}
      </div>
    </div>
  )
}

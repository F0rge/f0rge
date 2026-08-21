'use client'

import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import { FetchError } from '@f0rge/ui'
import { useMarkerCatalog, useMarkerHistory } from '@/lib/api/hooks'
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
  const [pinned, setPinned] = useState<string[]>([])

  useEffect(() => {
    function refresh() {
      setPinned(readPinned())
    }
    refresh()
    window.addEventListener('focus', refresh)
    window.addEventListener('storage', refresh)
    return () => {
      window.removeEventListener('focus', refresh)
      window.removeEventListener('storage', refresh)
    }
  }, [])

  return pinned
}

function PinnedMarkerCard({ canonicalName }: { canonicalName: string }) {
  const { data: points, isLoading, isError, refetch } = useMarkerHistory(canonicalName)
  const { data: catalog } = useMarkerCatalog()
  const displayName =
    catalog?.find((m) => m.canonical_name === canonicalName)?.display_name ?? canonicalName

  if (isLoading) {
    return (
      <div
        role="status"
        aria-label={`Loading ${displayName}`}
        className="flex items-center justify-center rounded-xl bg-card p-3 ring-1 ring-foreground/10"
      >
        <Loader2 className="size-4 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (isError) {
    return (
      <FetchError message={`Failed to load ${displayName}.`} onRetry={() => refetch()} />
    )
  }

  const numericPoints = (points ?? []).filter((p) => p.value !== null)
  if (numericPoints.length === 0) return null

  const latest = numericPoints[numericPoints.length - 1]
  const trendSeries: SignalsTrendSeries = {
    key: canonicalName,
    label: displayName,
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

  if (series.length === 0 && pinnedMarkers.length === 0) {
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
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {pinnedMarkers.map((canonical) => (
              <PinnedMarkerCard key={canonical} canonicalName={canonical} />
            ))}
          </div>
        </div>
      )}
      {series.length > 0 && (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {series.map((s) => (
            <SignalsTrendCard key={s.key} series={s} />
          ))}
        </div>
      )}
    </div>
  )
}

'use client'

import { Loader2 } from 'lucide-react'
import { useInsightsTrends } from '@/lib/api/hooks'
import { TrendCard } from './trend-card'

interface Props {
  start: string
  end: string
}

export function TrendGrid({ start, end }: Props) {
  const { data, isLoading, isError } = useInsightsTrends(start, end)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (isError) {
    return (
      <p className="py-4 text-sm text-destructive">
        Failed to load trend data.
      </p>
    )
  }

  if (!data || data.series.length === 0) {
    return (
      <p className="py-4 text-sm text-muted-foreground">No trend data available.</p>
    )
  }

  return (
    <div className="grid grid-cols-2 gap-2">
      {data.series.map((s) => (
        <TrendCard key={s.key} series={s} />
      ))}
    </div>
  )
}

'use client'

import { LineChart, Line, ResponsiveContainer } from 'recharts'
import { useMarkerHistory } from '@/lib/api/hooks'

interface MarkerSparklineProps {
  canonicalName: string
}

export function MarkerSparkline({ canonicalName }: MarkerSparklineProps) {
  const { data, isLoading } = useMarkerHistory(canonicalName)

  if (isLoading) {
    return <div className="h-7 w-14 animate-pulse rounded bg-muted" />
  }

  const points = (data ?? [])
    .filter((p) => p.value !== null)
    .map((p) => ({ v: p.value }))

  if (points.length < 2) {
    return <div className="h-7 w-14 rounded bg-muted/40" />
  }

  return (
    <ResponsiveContainer width={56} height={28}>
      <LineChart data={points}>
        <Line
          type="monotone"
          dataKey="v"
          stroke="currentColor"
          strokeWidth={1.5}
          dot={false}
          className="text-primary"
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

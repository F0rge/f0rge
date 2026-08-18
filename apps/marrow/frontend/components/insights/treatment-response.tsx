'use client'

import { Loader2 } from 'lucide-react'
import { cn } from '@f0rge/ui'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { useInsightsTreatmentResponse } from '@/lib/api/hooks'
import type { TreatmentResponseRow } from '@/lib/api/types'
import { chartStroke, statusText } from '@/lib/ui/status'

interface Props {
  outcome: string
}

function TreatmentBar({ row }: { row: TreatmentResponseRow }) {
  const chartData = [
    { phase: 'Baseline', value: row.baseline_mean, n: row.baseline_n },
    { phase: 'During', value: row.during_mean, n: row.during_n },
    ...(row.after_mean !== null
      ? [{ phase: 'After', value: row.after_mean, n: row.after_n }]
      : []),
  ].filter((d) => d.value !== null)

  const deltaLabel =
    row.delta_during_vs_baseline !== null
      ? `${row.delta_during_vs_baseline > 0 ? '+' : ''}${row.delta_during_vs_baseline.toFixed(2)}`
      : null

  return (
    <div className="rounded-xl bg-card p-3 ring-1 ring-foreground/10">
      <div className="mb-2 flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold">{row.name}</p>
          <p className="text-xs text-muted-foreground capitalize">{row.type}</p>
        </div>
        {deltaLabel && (
          <span
            className={cn(
              'text-sm font-semibold',
              row.delta_during_vs_baseline! > 0 ? statusText.ok : statusText.destructive,
            )}
          >
            {deltaLabel}
          </span>
        )}
      </div>

      <ResponsiveContainer width="100%" height={120}>
        <BarChart data={chartData} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
          <XAxis dataKey="phase" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip
            contentStyle={{ fontSize: 12 }}
            formatter={(val) =>
              typeof val === 'number' ? val.toFixed(2) : val
            }
          />
          <Bar dataKey="value" name="Mean" radius={[4, 4, 0, 0]}>
            {chartData.map((entry, idx) => (
              <Cell
                key={idx}
                fill={
                  entry.phase === 'Baseline'
                    ? chartStroke.muted
                    : entry.phase === 'During'
                      ? chartStroke[1]
                      : chartStroke.ok
                }
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      <div className="mt-1 flex gap-3 text-xs text-muted-foreground">
        <span>n baseline={row.baseline_n}</span>
        <span>n during={row.during_n}</span>
        {row.after_mean !== null && <span>n after={row.after_n}</span>}
      </div>
    </div>
  )
}

export function TreatmentResponse({ outcome }: Props) {
  const { data, isLoading, isError } = useInsightsTreatmentResponse(outcome)

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-6">
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (isError) {
    return (
      <p className="text-sm text-destructive">Failed to load treatment data.</p>
    )
  }

  if (!data || data.rows.length === 0) {
    return (
      <p className="py-4 text-sm text-muted-foreground">
        No treatments with sufficient data yet.
      </p>
    )
  }

  return (
    <div className="space-y-3">
      {data.rows.map((row) => (
        <TreatmentBar key={row.treatment_id} row={row} />
      ))}
    </div>
  )
}

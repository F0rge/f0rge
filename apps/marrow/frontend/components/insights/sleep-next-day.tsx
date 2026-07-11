'use client'

import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { useInsightsSleepNextDay } from '@/lib/api/hooks'

interface Props {
  outcome: string
  start: string
  end: string
}

const METRIC_OPTIONS = [
  { value: 'hm_sleep_rem_min', label: 'REM minutes' },
  { value: 'hm_sleep_deep_min', label: 'Deep sleep minutes' },
  { value: 'hm_sleep_efficiency', label: 'Sleep efficiency' },
] as const

type MetricValue = (typeof METRIC_OPTIONS)[number]['value']

export function SleepNextDay({ outcome, start, end }: Props) {
  const [metric, setMetric] = useState<MetricValue>('hm_sleep_efficiency')

  const { data, isLoading, isError } = useInsightsSleepNextDay(
    outcome,
    metric,
    start,
    end,
  )

  const selectedLabel =
    METRIC_OPTIONS.find((m) => m.value === metric)?.label ?? metric

  const chartData = data?.points.map((p) => ({
    x: p.sleep_value,
    y: p.next_day_outcome,
  })) ?? []

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Select value={metric} onValueChange={(v) => setMetric(v as MetricValue)}>
          <SelectTrigger className="h-8 w-auto text-sm">
            <SelectValue>{selectedLabel}</SelectValue>
          </SelectTrigger>
          <SelectContent>
            {METRIC_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {data && (
          <div className="flex items-center gap-2">
            <Badge variant="secondary">
              ρ = {data.rho !== null ? data.rho.toFixed(3) : '—'}
            </Badge>
            <Badge variant="outline">n = {data.n}</Badge>
          </div>
        )}
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="size-5 animate-spin text-muted-foreground" />
        </div>
      )}

      {isError && (
        <p className="text-sm text-destructive">Failed to load sleep data.</p>
      )}

      {data && !isLoading && chartData.length === 0 && (
        <p className="py-4 text-sm text-muted-foreground">No paired data available.</p>
      )}

      {data && !isLoading && chartData.length > 0 && (
        <div>
          <ResponsiveContainer width="100%" height={220}>
            <ScatterChart margin={{ top: 4, right: 8, left: -16, bottom: 16 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis
                type="number"
                dataKey="x"
                name={selectedLabel}
                tick={{ fontSize: 10 }}
                label={{
                  value: selectedLabel,
                  position: 'insideBottom',
                  offset: -10,
                  fontSize: 10,
                }}
              />
              <YAxis
                type="number"
                dataKey="y"
                name="Next-day outcome"
                tick={{ fontSize: 10 }}
              />
              <Tooltip
                cursor={{ strokeDasharray: '3 3' }}
                contentStyle={{ fontSize: 12 }}
                formatter={(val) => (typeof val === 'number' ? val.toFixed(2) : val)}
              />
              <Scatter data={chartData} fill="#6366f1" opacity={0.7} />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

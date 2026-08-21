'use client'

import {
  LineChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { TodayCalibrationPoint } from '@/lib/api/types/signals'
import { chartStroke } from '@/lib/ui/status'

interface Props {
  series: TodayCalibrationPoint[]
}

export function CalibrationStrip({ series }: Props) {
  const data = series.map((p) => ({
    date: p.date.slice(5),
    predicted: p.predicted,
    actual: p.actual,
  }))

  if (data.length < 2) {
    return (
      <section aria-label="Calibration">
        <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Calibration
        </h2>
        <p className="mb-2 text-xs text-muted-foreground">Predicted vs logged</p>
        <p className="text-sm text-muted-foreground">Not enough calibration history.</p>
      </section>
    )
  }

  return (
    <section aria-label="Calibration">
      <h2 className="mb-1 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        Calibration
      </h2>
      <p className="mb-2 text-xs text-muted-foreground">Predicted vs logged</p>
      <div className="rounded-xl bg-card p-3 ring-1 ring-foreground/10">
        <ResponsiveContainer width="100%" height={120}>
          <LineChart data={data} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
            <XAxis dataKey="date" tick={{ fontSize: 9 }} interval="preserveStartEnd" />
            <YAxis tick={{ fontSize: 9 }} />
            <Tooltip contentStyle={{ fontSize: 11 }} />
            <Line
              type="monotone"
              dataKey="predicted"
              stroke={chartStroke[1]}
              strokeWidth={1.5}
              dot={false}
              name="Predicted"
            />
            <Line
              type="monotone"
              dataKey="actual"
              stroke={chartStroke.ok}
              strokeWidth={1.5}
              dot={false}
              name="Actual"
              connectNulls={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}

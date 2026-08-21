import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { SignalsTrendSeries } from '@/lib/api/types/signals'
import { chartStroke } from '@/lib/ui/status'
import { SignalsChartTooltip, chartAxisTick } from './chart-tooltip'

export function TrendSparkline({ points }: { points: SignalsTrendSeries['points'] }) {
  const data = points
    .filter((p) => p.value !== null)
    .slice(-30)
    .map((p) => ({ date: p.date, v: p.value }))

  if (data.length < 2) {
    return (
      <div className="flex h-10 items-center justify-center text-xs text-muted-foreground">
        not enough data
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={40}>
      <LineChart data={data}>
        <Line
          type="monotone"
          dataKey="v"
          stroke={chartStroke[1]}
          strokeWidth={1.5}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

export function TrendFullChart({ series }: { series: SignalsTrendSeries }) {
  const data = series.points
    .filter((p) => p.value !== null || p.rolling_avg_7 !== null)
    .map((p) => ({
      date: p.date.slice(5),
      value: p.value,
      avg7: p.rolling_avg_7,
    }))

  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
        <XAxis dataKey="date" tick={chartAxisTick} interval="preserveStartEnd" />
        <YAxis tick={chartAxisTick} />
        <Tooltip content={<SignalsChartTooltip />} />
        <Line
          type="monotone"
          dataKey="value"
          stroke={chartStroke[1]}
          strokeWidth={1.5}
          dot={false}
          name="Value"
        />
        <Line
          type="monotone"
          dataKey="avg7"
          stroke={chartStroke.muted}
          strokeWidth={1.5}
          dot={false}
          strokeDasharray="4 2"
          name="7-day avg"
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

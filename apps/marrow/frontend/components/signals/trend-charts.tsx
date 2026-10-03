import { Line, LineChart, XAxis, YAxis } from 'recharts'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@f0rge/ui'
import type { SignalsTrendSeries } from '@/lib/api/types/signals'

const sparkConfig = {
  value: { label: 'Value', color: 'var(--chart-1)' },
} satisfies ChartConfig

const fullConfig = {
  value: { label: 'Value', color: 'var(--chart-1)' },
  avg7: { label: '7-day avg', color: 'var(--muted-foreground)' },
} satisfies ChartConfig

export function TrendSparkline({ points }: { points: SignalsTrendSeries['points'] }) {
  const data = points
    .filter((p) => p.value !== null)
    .slice(-30)
    .map((p) => ({ date: p.date, value: p.value }))

  if (data.length < 2) {
    return (
      <div className="flex h-10 items-center justify-center text-xs text-muted-foreground">
        not enough data
      </div>
    )
  }

  return (
    <ChartContainer config={sparkConfig} className="aspect-auto h-10 w-full">
      <LineChart data={data} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
        <Line
          type="monotone"
          dataKey="value"
          stroke="var(--color-value)"
          strokeWidth={1.5}
          dot={false}
        />
      </LineChart>
    </ChartContainer>
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
    <ChartContainer config={fullConfig} className="aspect-auto h-[200px] w-full">
      <LineChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
        <XAxis dataKey="date" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
        <YAxis tick={{ fontSize: 10 }} width={32} />
        <ChartTooltip content={<ChartTooltipContent />} />
        <Line
          type="monotone"
          dataKey="value"
          stroke="var(--color-value)"
          strokeWidth={1.5}
          dot={false}
          name="Value"
        />
        <Line
          type="monotone"
          dataKey="avg7"
          stroke="var(--color-avg7)"
          strokeWidth={1.5}
          dot={false}
          strokeDasharray="4 2"
          name="7-day avg"
        />
      </LineChart>
    </ChartContainer>
  )
}

'use client'

export const chartAxisTick = {
  fontSize: 10,
  fill: 'var(--muted-foreground)',
} as const

type TooltipItem = { name?: string; value?: unknown }

/** Theme-aware Recharts tooltip — matches labs marker history. */
export function SignalsChartTooltip({
  payload,
  label,
}: {
  payload?: ReadonlyArray<TooltipItem>
  label?: string | number
}) {
  if (!payload?.length) return null
  return (
    <div className="rounded-lg border border-border bg-background px-2 py-1 text-xs shadow-sm">
      {label != null && label !== '' ? <p className="font-medium">{String(label)}</p> : null}
      {payload.map((item) => (
        <p key={String(item.name)}>
          {item.name}: {item.value == null ? '—' : String(item.value)}
        </p>
      ))}
    </div>
  )
}

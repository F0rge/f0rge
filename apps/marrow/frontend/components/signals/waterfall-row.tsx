import { cn } from '@f0rge/ui'

export function WaterfallRow({
  label,
  value,
  detail,
  tone,
  barWidth,
  barClass,
  signed = true,
}: {
  label: string
  value: number
  detail?: string | null
  tone?: string
  barWidth?: number
  barClass?: string
  signed?: boolean
}) {
  const display = signed
    ? value >= 0
      ? `+${value}`
      : String(value)
    : String(value)
  return (
    <div className="space-y-0.5">
      <div className="flex items-center gap-2 text-sm">
        <span className="w-24 shrink-0 truncate text-muted-foreground">{label}</span>
        <div className="relative h-5 min-w-0 flex-1 rounded bg-muted/50">
          {barWidth != null && barWidth > 0 && (
            <div
              className={cn(
                'absolute top-0 h-full rounded',
                value >= 0 ? 'left-1/2' : 'right-1/2',
                barClass ?? 'bg-muted-foreground/70',
              )}
              style={{ width: `${barWidth}%` }}
            />
          )}
        </div>
        <span className={cn('w-14 shrink-0 text-right tabular-nums', tone)}>
          {display}
        </span>
      </div>
      {detail ? (
        <p className="text-xs text-muted-foreground">{detail}</p>
      ) : null}
    </div>
  )
}

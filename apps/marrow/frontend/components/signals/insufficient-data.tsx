import type { SignalsMeta } from '@/lib/api/types/signals'

interface Props {
  meta: SignalsMeta
}

export function InsufficientDataBanner({ meta }: Props) {
  if (!meta.insufficient_data) return null

  return (
    <div
      role="status"
      className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm"
    >
      <p className="font-medium text-foreground">Not enough data yet</p>
      <p className="mt-1 text-muted-foreground">
        {meta.insufficient_reason ??
          `Need more check-ins (${meta.days_usable} usable days of ${meta.days_total} in range).`}
      </p>
    </div>
  )
}

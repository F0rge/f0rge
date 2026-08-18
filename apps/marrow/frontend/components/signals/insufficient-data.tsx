import Link from 'next/link'
import type { SignalsMeta } from '@/lib/api/types/signals'
import { SectionMark } from '@/components/shared/color-artifact'

interface Props {
  meta: SignalsMeta
}

export function InsufficientDataBanner({ meta }: Props) {
  if (!meta.insufficient_data) return null

  return (
    <div
      role="status"
      className="flex gap-3 rounded-xl border border-warn/30 bg-warn/10 px-4 py-3 text-sm"
    >
      <SectionMark className="mt-0.5" />
      <div className="min-w-0 flex-1">
        <p className="font-medium text-foreground">Not enough data yet</p>
        <p className="mt-1 text-muted-foreground">
          {meta.insufficient_reason ??
            `Need more check-ins (${meta.days_usable} usable days of ${meta.days_total} in range).`}
        </p>
        <Link
          href="/checkin"
          className="mt-2 inline-block text-sm font-medium text-foreground underline-offset-4 hover:underline"
        >
          Log a check-in
        </Link>
      </div>
    </div>
  )
}

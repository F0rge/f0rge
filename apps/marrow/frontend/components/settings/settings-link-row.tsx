/**
 * SettingsLinkRow — a navigation entry in the /settings list.
 *
 * Anatomy (mirrors customize/hub-row): [icon tile] [title + description flex-1] [badge?] [chevron]
 */

import Link from 'next/link'
import { ChevronRight } from 'lucide-react'
import { cn } from '@f0rge/ui'
import { IconWell } from '@/components/shared/color-artifact'
import type { ReactNode } from 'react'

function CountBadge({ count }: { count: number }) {
  if (count <= 0) return null
  const label = count > 9 ? '9+' : String(count)
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-full bg-chart-1 text-[10px] font-semibold leading-none text-foreground',
        label.length === 1 ? 'size-[18px]' : 'h-[18px] min-w-[18px] px-1',
      )}
      aria-hidden
    >
      {label}
    </span>
  )
}

interface SettingsLinkRowProps {
  href: string
  /** 16px icon rendered in a 36px chromatic well. */
  icon: ReactNode
  title: string
  description: string
  /** Pending count — hidden when 0. */
  badge?: number
}

export function SettingsLinkRow({ href, icon, title, description, badge = 0 }: SettingsLinkRowProps) {
  return (
    <Link
      href={href}
      className="flex items-center gap-3 px-4 py-3.5 transition-colors hover:bg-muted/50 active:bg-muted"
      aria-label={badge > 0 ? `${title}, ${badge} pending` : undefined}
    >
      <IconWell>{icon}</IconWell>
      <div className="min-w-0 flex-1">
        <span className="text-sm font-medium">{title}</span>
        <p className="mt-0.5 text-xs leading-snug text-muted-foreground">{description}</p>
      </div>
      <CountBadge count={badge} />
      <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
    </Link>
  )
}

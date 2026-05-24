/**
 * HubRow — a single entry in the /customize hub list.
 *
 * Anatomy: [icon] [title + description flex-1] [tier pill + chevron]
 */

import Link from 'next/link'
import { ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { TierPill, type Tier } from './tier-pill'
import type { ReactNode } from 'react'

interface HubRowProps {
  /** Route to push when row is tapped. */
  href: string
  /** 24px icon element rendered in a muted tile. */
  icon: ReactNode
  title: string
  description: string
  tier: Tier
  /** When true, renders as a muted non-interactive row with "Coming soon" label. */
  comingSoon?: boolean
}

export function HubRow({
  href,
  icon,
  title,
  description,
  tier,
  comingSoon = false,
}: HubRowProps) {
  const inner = (
    <div
      className={cn(
        'flex items-center gap-3 px-4 py-3.5',
        'border-t border-muted first:border-t-0',
        comingSoon ? 'opacity-50' : 'hover:bg-muted/50 active:bg-muted transition-colors',
      )}
    >
      {/* Icon tile */}
      <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
        {icon}
      </span>

      {/* Title + description */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{title}</span>
          <TierPill tier={tier} />
          {comingSoon && (
            <span className="text-[9px] font-semibold uppercase tracking-wider text-muted-foreground">
              Soon
            </span>
          )}
        </div>
        <p className="mt-0.5 text-xs text-muted-foreground leading-snug">{description}</p>
      </div>

      {/* Chevron */}
      {!comingSoon && (
        <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
      )}
    </div>
  )

  if (comingSoon) {
    return <div aria-disabled="true">{inner}</div>
  }

  return <Link href={href}>{inner}</Link>
}

/**
 * HubRow — a single entry in the /customize hub list.
 *
 * Anatomy: [icon] [title + description flex-1] [tier pill + chevron]
 */

import Link from 'next/link'
import { ChevronRight } from 'lucide-react'
import { cn } from '@f0rge/ui'
import { IconWell } from '@/components/shared/color-artifact'
import { toneFromTier } from '@/lib/ui/status'
import { TierPill, type Tier } from './tier-pill'
import type { ReactNode } from 'react'

interface HubRowProps {
  /** Route to push when row is tapped. */
  href: string
  /** 16px icon rendered in a 36px chromatic well. */
  icon: ReactNode
  title: string
  description: string
  /** Omit for meta rows (e.g. Reorder & visibility) that span all tiers. */
  tier?: Tier
  /** When true, renders as a muted non-interactive row with "Coming soon" label. */
  comingSoon?: boolean
  /** Tile variant for desktop grid cards (no list dividers). */
  variant?: 'list' | 'tile'
}

export function HubRow({
  href,
  icon,
  title,
  description,
  tier,
  comingSoon = false,
  variant = 'list',
}: HubRowProps) {
  const inner = (
    <div
      className={cn(
        'flex items-center gap-3 px-4 py-3.5',
        variant === 'list' && 'border-t border-muted first:border-t-0',
        variant === 'tile' && 'h-full',
        comingSoon ? 'opacity-50' : 'hover:bg-muted/50 active:bg-muted transition-colors',
      )}
    >
      <IconWell tone={tier ? toneFromTier(tier) : undefined} muted={comingSoon}>
        {icon}
      </IconWell>

      {/* Title + description */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{title}</span>
          {tier && <TierPill tier={tier} />}
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

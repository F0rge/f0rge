/**
 * HubRow — a single entry in the /customize hub list.
 *
 * Anatomy: [icon tile] [title + description flex-1] [tier pill + chevron]
 */

import Link from 'next/link'
import { ChevronRight } from 'lucide-react'
import {
  cn,
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemMedia,
  ItemTitle,
} from '@f0rge/ui'
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
    <Item
      variant="default"
      size="sm"
      className={cn(
        'rounded-none border-0 px-4 py-3.5',
        variant === 'list' && 'border-t border-muted first:border-t-0',
        variant === 'tile' && 'h-full',
        comingSoon ? 'opacity-50' : 'hover:bg-muted/50 active:bg-muted',
      )}
    >
      <ItemMedia variant="icon">
        <IconWell tone={tier ? toneFromTier(tier) : undefined} muted={comingSoon}>
          {icon}
        </IconWell>
      </ItemMedia>
      <ItemContent>
        <ItemTitle className="flex flex-wrap items-center gap-2 font-medium">
          {title}
          {tier && <TierPill tier={tier} />}
          {comingSoon && (
            <span className="text-[9px] font-semibold uppercase tracking-wider text-muted-foreground">
              Soon
            </span>
          )}
        </ItemTitle>
        <ItemDescription>{description}</ItemDescription>
      </ItemContent>
      {!comingSoon && (
        <ItemActions>
          <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
        </ItemActions>
      )}
    </Item>
  )

  if (comingSoon) {
    return <div aria-disabled="true">{inner}</div>
  }

  return <Link href={href} className="block">{inner}</Link>
}

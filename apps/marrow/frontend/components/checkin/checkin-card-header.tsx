'use client'

import { Eye, EyeOff } from 'lucide-react'
import { CardHeader, CardTitle, CardAction } from '@f0rge/ui'
import { TierPill, type Tier } from '@/components/customize/tier-pill'
import { LG_DESKTOP_QUERY, useMediaQuery } from '@f0rge/ui'
import { cn } from '@f0rge/ui'
import { SectionMark } from '@/components/shared/color-artifact'
import { toneFromTier } from '@/lib/ui/status'

interface CheckinCardHeaderProps {
  title: string
  tier?: Tier
  collapsed: boolean
  onToggleCollapsed: () => void
}

export function CheckinCardHeader({
  title,
  tier,
  collapsed,
  onToggleCollapsed,
}: CheckinCardHeaderProps) {
  const isDesktop = useMediaQuery(LG_DESKTOP_QUERY)

  return (
    <CardHeader>
      <CardTitle
        className={cn(
          'flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-muted-foreground',
        )}
      >
        <SectionMark tone={tier ? toneFromTier(tier) : undefined} />
        {title}
        {tier !== undefined && <TierPill tier={tier} />}
      </CardTitle>
      {!isDesktop && (
        <CardAction>
          <button
            type="button"
            onClick={onToggleCollapsed}
            aria-expanded={!collapsed}
            aria-label={collapsed ? `Show ${title}` : `Hide ${title}`}
            className={cn(
              'flex size-8 items-center justify-center rounded-full transition-colors',
              'text-muted-foreground hover:bg-muted hover:text-foreground',
            )}
          >
            {collapsed ? (
              <Eye className="size-4" />
            ) : (
              <EyeOff className="size-4" />
            )}
          </button>
        </CardAction>
      )}
    </CardHeader>
  )
}

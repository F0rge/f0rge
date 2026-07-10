'use client'

import { Eye, EyeOff } from 'lucide-react'
import { CardHeader, CardTitle, CardAction } from '@/components/ui/card'
import { TierPill, type Tier } from '@/components/customize/tier-pill'
import { cn } from '@/lib/utils'

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
  return (
    <CardHeader>
      <CardTitle
        className={cn(
          'flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-muted-foreground',
        )}
      >
        {title}
        {tier !== undefined && <TierPill tier={tier} />}
      </CardTitle>
      <CardAction>
        <button
          type="button"
          onClick={onToggleCollapsed}
          aria-expanded={!collapsed}
          aria-label={collapsed ? `Show ${title}` : `Hide ${title}`}
          className={cn(
            'flex size-8 items-center justify-center rounded-md transition-colors',
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
    </CardHeader>
  )
}

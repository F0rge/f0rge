/**
 * SettingsLinkRow — a navigation entry in the /settings list.
 *
 * Anatomy (mirrors customize/hub-row): [icon tile] [title + description flex-1] [badge?] [chevron]
 */

import Link from 'next/link'
import { ChevronRight } from 'lucide-react'
import {
  Badge,
  cn,
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemMedia,
  ItemTitle,
} from '@f0rge/ui'
import { IconWell } from '@/components/shared/color-artifact'
import type { ReactNode } from 'react'

function CountBadge({ count }: { count: number }) {
  if (count <= 0) return null
  const label = count > 9 ? '9+' : String(count)
  return (
    <Badge
      variant="secondary"
      className={cn(
        'h-[18px] min-w-[18px] justify-center rounded-full bg-chart-1 px-1 text-[10px] font-semibold text-foreground',
        label.length === 1 && 'size-[18px] px-0',
      )}
      aria-hidden
    >
      {label}
    </Badge>
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
    <Item
      variant="default"
      size="sm"
      className="rounded-none border-0 px-4 py-3.5 transition-colors hover:bg-muted/50 active:bg-muted"
      render={
        <Link
          href={href}
          aria-label={badge > 0 ? `${title}, ${badge} pending` : undefined}
        />
      }
    >
      <ItemMedia variant="icon">
        <IconWell>{icon}</IconWell>
      </ItemMedia>
      <ItemContent>
        <ItemTitle className="font-medium">{title}</ItemTitle>
        <ItemDescription>{description}</ItemDescription>
      </ItemContent>
      <ItemActions>
        <CountBadge count={badge} />
        <ChevronRight className="size-4 shrink-0 text-muted-foreground" />
      </ItemActions>
    </Item>
  )
}

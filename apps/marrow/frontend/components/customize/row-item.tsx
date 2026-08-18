/**
 * RowItem — shared row anatomy for /customize/* detail screens.
 *
 * Anatomy: [drag-handle 16px] [icon 32px] [name + meta flex-1] [actions ≤2]
 *
 * All slots are optional — omit the ones you don't need.
 */

import { cn } from '@f0rge/ui'
import { IconWell } from '@/components/shared/color-artifact'
import { toneFromTier, type CustomizeTier } from '@/lib/ui/status'
import type { ReactNode } from 'react'

interface RowItemProps {
  /** Drag handle element (e.g. GripVertical button with dnd-kit listeners). */
  dragHandle?: ReactNode
  /** 32×32 icon tile. */
  icon?: ReactNode
  /** Primary label text. */
  label: string
  /** Secondary meta line rendered below the label (pills, counts, descriptions). */
  meta?: ReactNode
  /** Up to 2 action elements on the right side. */
  actions?: ReactNode
  /** Whether the row should appear dimmed (e.g. hidden or archived state). */
  dimmed?: boolean
  /** When set, the icon well matches the page's governance tier. */
  tier?: CustomizeTier
  className?: string
}

export function RowItem({
  dragHandle,
  icon,
  label,
  meta,
  actions,
  dimmed = false,
  tier,
  className,
}: RowItemProps) {
  return (
    <div
      className={cn(
        'flex items-center gap-3 py-2.5 border-t border-muted first:border-t-0',
        dimmed && 'opacity-60',
        className,
      )}
    >
      {dragHandle && (
        <span className="flex w-4 shrink-0 items-center justify-center text-muted-foreground/40">
          {dragHandle}
        </span>
      )}

      {icon && (
        <IconWell
          tone={tier ? toneFromTier(tier) : undefined}
          className="size-8 rounded-full"
        >
          {icon}
        </IconWell>
      )}

      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium leading-snug">{label}</div>
        {meta && (
          <div className="mt-0.5 flex items-center gap-1.5">{meta}</div>
        )}
      </div>

      {actions && (
        <div className="flex shrink-0 items-center gap-1">
          {actions}
        </div>
      )}
    </div>
  )
}

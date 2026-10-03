'use client'

/**
 * Sortable row for the /customize/trackers drag-reorder list.
 * Parent wraps rows in `<Sortable>` from `@f0rge/ui`.
 */

import { GripVertical, Pencil, Trash2 } from 'lucide-react'
import { Button, SortableItem, SortableItemHandle } from '@f0rge/ui'
import { RowItem } from '@/components/customize/row-item'
import { ICON_COMPONENT_MAP } from '@/components/checkin/cards/components/IconPicker'
import type { Tracker } from '@/lib/api/types'

interface SortableTrackerRowProps {
  tracker: Tracker
  onEdit: (tracker: Tracker) => void
  onArchive: (tracker: Tracker) => void
  overlay?: boolean
}

export function SortableTrackerRow({ tracker, onEdit, onArchive, overlay = false }: SortableTrackerRowProps) {
  const IconComponent = tracker.icon ? ICON_COMPONENT_MAP[tracker.icon] : null
  const dragHandle = overlay ? (
    <span className="text-muted-foreground/40">
      <GripVertical className="size-4" />
    </span>
  ) : (
    <SortableItemHandle
      render={
        <button
          type="button"
          aria-label="Drag to reorder"
          className="touch-none text-muted-foreground/40 hover:text-muted-foreground"
        />
      }
    >
      <GripVertical className="size-4" />
    </SortableItemHandle>
  )

  const row = (
    <RowItem
      dragHandle={dragHandle}
      icon={IconComponent ? <IconComponent className="size-4" /> : undefined}
      label={tracker.name}
      meta={`${tracker.kind} · ${tracker.unit}`}
      actions={
        overlay
          ? undefined
          : (
            <>
              <Button
                variant="ghost"
                size="icon"
                className="size-8 text-muted-foreground hover:text-foreground"
                aria-label={`Edit ${tracker.name}`}
                onClick={() => onEdit(tracker)}
              >
                <Pencil className="size-3.5" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="size-8 text-muted-foreground hover:text-destructive"
                aria-label={`Archive ${tracker.name}`}
                onClick={() => onArchive(tracker)}
              >
                <Trash2 className="size-3.5" />
              </Button>
            </>
          )
      }
      className={overlay ? 'rounded-lg border border-border bg-card shadow-md' : undefined}
    />
  )

  if (overlay) return row

  return (
    <SortableItem value={String(tracker.id)} className="border-b border-border last:border-b-0">
      {row}
    </SortableItem>
  )
}

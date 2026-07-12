'use client'

/**
 * Sortable row + ghost row for the /customize/trackers drag-reorder list.
 *
 * Split out of trackers-client.tsx to keep that file focused on page-level
 * state. Both helpers are dnd-kit specific: SortableTrackerRow wires the
 * useSortable hook + drag handle; GhostRow renders inside <DragOverlay> with
 * no listeners (the overlay's parent <div style={{ width }}> sizes it).
 */

import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical, Pencil, Trash2 } from 'lucide-react'
import { Button } from '@f0rge/ui'
import { RowItem } from '@/components/customize/row-item'
import { ICON_COMPONENT_MAP } from '@/components/checkin/cards/components/IconPicker'
import type { Tracker } from '@/lib/api/types'

interface SortableTrackerRowProps {
  tracker: Tracker
  onEdit: (tracker: Tracker) => void
  onArchive: (tracker: Tracker) => void
}

export function SortableTrackerRow({ tracker, onEdit, onArchive }: SortableTrackerRowProps) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: tracker.id,
  })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  const IconComponent = tracker.icon ? ICON_COMPONENT_MAP[tracker.icon] : null

  return (
    <div ref={setNodeRef} style={style} className={isDragging ? 'opacity-30' : undefined}>
      <RowItem
        dragHandle={
          <button
            type="button"
            aria-label="Drag to reorder"
            className="touch-none cursor-grab active:cursor-grabbing text-muted-foreground/40 hover:text-muted-foreground"
            {...listeners}
            {...attributes}
          >
            <GripVertical className="size-4" />
          </button>
        }
        icon={
          IconComponent ? <IconComponent className="size-4 text-muted-foreground" /> : undefined
        }
        label={tracker.name}
        meta={
          <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            {tracker.kind}
            {tracker.unit ? ` · ${tracker.unit}` : ''}
          </span>
        }
        actions={
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
        }
      />
    </div>
  )
}

interface GhostRowProps {
  tracker: Tracker
}

export function GhostRow({ tracker }: GhostRowProps) {
  const IconComponent = tracker.icon ? ICON_COMPONENT_MAP[tracker.icon] : null

  return (
    <RowItem
      dragHandle={
        <span className="text-muted-foreground/40">
          <GripVertical className="size-4" />
        </span>
      }
      icon={
        IconComponent ? <IconComponent className="size-4 text-muted-foreground" /> : undefined
      }
      label={tracker.name}
      meta={
        <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          {tracker.kind}
          {tracker.unit ? ` · ${tracker.unit}` : ''}
        </span>
      }
      className="rounded-lg border border-border bg-card shadow-md"
    />
  )
}

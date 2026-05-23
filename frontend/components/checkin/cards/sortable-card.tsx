'use client'

/**
 * SortableCard — dnd-kit sortable wrapper for check-in grid cards.
 *
 * The drag handle (GripVertical icon) is wired to useSortable listeners/attributes,
 * NOT the whole card, so taps and clicks inside cards still work normally.
 *
 * Desktop (lg+): handle is hidden, revealed on parent card hover via group-hover.
 * Mobile (<lg): handle is always visible — touch users can't hover; long-press
 *               350ms (via dnd-kit TouchSensor activation constraint) starts drag.
 *
 * The col-span class is applied to this wrapper (not the inner Card), since the
 * wrapper IS the grid item. The inner Card uses `h-full` to fill the wrapper.
 */

import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import type { CardId } from '@/lib/checkin/card-order'

interface SortableCardProps {
  id: CardId
  /** col-span classes that were previously on the inner Card element. */
  colSpanClass: string
  children: ReactNode
}

export function SortableCard({ id, colSpanClass, children }: SortableCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        colSpanClass,
        'group relative',
        isDragging && 'z-50 opacity-50',
      )}
    >
      {/* Drag handle — hidden on desktop until card is hovered; always visible on touch */}
      <button
        {...attributes}
        {...listeners}
        aria-label="Drag to reorder card"
        className={cn(
          'absolute right-2 top-2 z-10 flex size-7 items-center justify-center rounded-md',
          'text-muted-foreground/40 transition-opacity',
          // Mobile (<lg): always visible — touch users can't hover.
          // Desktop (lg+): hidden until card is hovered.
          'opacity-100 lg:opacity-0 lg:group-hover:opacity-100',
          // Active drag: full opacity regardless of breakpoint.
          isDragging && 'opacity-100',
          'cursor-grab active:cursor-grabbing',
        )}
      >
        <GripVertical className="size-4" />
      </button>

      {children}
    </div>
  )
}

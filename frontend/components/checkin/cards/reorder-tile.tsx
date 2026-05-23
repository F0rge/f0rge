'use client'

/**
 * ReorderTile — compact card placeholder shown in reorder mode.
 *
 * In reorder mode, the full card content is replaced with a fixed-height tile
 * showing just the card icon and title. All tiles have the same height so
 * there is zero morphing or stretching during drag.
 *
 * Up/down arrow buttons provide a tap-to-move fallback for accessibility
 * (no drag required).
 */

import { ChevronUp, ChevronDown, GripVertical } from 'lucide-react'
import type { DraggableSyntheticListeners } from '@dnd-kit/core'
import type { DraggableAttributes } from '@dnd-kit/core'
import { cn } from '@/lib/utils'
import type { CardId } from '@/lib/checkin/card-order'
import type { ReactNode } from 'react'

export interface CardMeta {
  id: CardId
  icon: ReactNode
  label: string
}

interface ReorderTileProps {
  meta: CardMeta
  /** dnd-kit drag handle event listeners — spread onto the grip button */
  dragListeners: DraggableSyntheticListeners
  /** dnd-kit drag handle attributes (aria roles) — spread onto the grip button. Omit for overlay tiles. */
  dragAttributes?: DraggableAttributes
  isDragging: boolean
  isFirst: boolean
  isLast: boolean
  onMoveUp: () => void
  onMoveDown: () => void
}

export function ReorderTile({
  meta,
  dragListeners,
  dragAttributes,
  isDragging,
  isFirst,
  isLast,
  onMoveUp,
  onMoveDown,
}: ReorderTileProps) {
  return (
    <div
      className={cn(
        'flex h-14 w-full items-center gap-3 rounded-lg border bg-card px-3',
        'transition-shadow',
        isDragging && 'shadow-lg ring-2 ring-primary/40',
      )}
    >
      {/* Drag grip — full touch target */}
      <button
        {...dragListeners}
        {...(dragAttributes ?? {})}
        aria-label={`Drag to reorder ${meta.label}`}
        className={cn(
          'flex size-8 shrink-0 items-center justify-center rounded-md',
          'text-muted-foreground/50 transition-colors hover:text-muted-foreground',
          'cursor-grab active:cursor-grabbing',
          'touch-none', // prevent scroll interference on the handle itself
        )}
      >
        <GripVertical className="size-4" />
      </button>

      {/* Icon */}
      <span className="flex size-7 shrink-0 items-center justify-center text-muted-foreground">
        {meta.icon}
      </span>

      {/* Label */}
      <span className="flex-1 text-sm font-medium">{meta.label}</span>

      {/* Up / down arrow buttons — tap-to-move fallback */}
      <div className="flex shrink-0 items-center gap-0.5">
        <button
          type="button"
          onClick={onMoveUp}
          disabled={isFirst}
          aria-label={`Move ${meta.label} up`}
          className={cn(
            'flex size-8 items-center justify-center rounded-md transition-colors',
            'text-muted-foreground hover:bg-muted hover:text-foreground',
            'disabled:pointer-events-none disabled:opacity-30',
          )}
        >
          <ChevronUp className="size-4" />
        </button>
        <button
          type="button"
          onClick={onMoveDown}
          disabled={isLast}
          aria-label={`Move ${meta.label} down`}
          className={cn(
            'flex size-8 items-center justify-center rounded-md transition-colors',
            'text-muted-foreground hover:bg-muted hover:text-foreground',
            'disabled:pointer-events-none disabled:opacity-30',
          )}
        >
          <ChevronDown className="size-4" />
        </button>
      </div>
    </div>
  )
}

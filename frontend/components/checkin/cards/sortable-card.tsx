'use client'

/**
 * SortableCard — dnd-kit sortable wrapper for check-in grid cards.
 *
 * Two modes:
 *  - Normal mode (isReorderMode=false): plain wrapper with no drag handles,
 *    no grip icons. Cards render at full content. dnd-kit is not active.
 *  - Reorder mode (isReorderMode=true): card content is replaced by a
 *    uniform-height ReorderTile (icon + label + up/down arrows + drag grip).
 *    All tiles have the same height — no morphing during drag.
 *
 * The col-span class always lives on this wrapper (not the inner Card) so
 * dnd-kit transforms apply to the correct grid item.
 */

import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import type { CardId } from '@/lib/checkin/card-order'
import { ReorderTile, type CardMeta } from './reorder-tile'

interface SortableCardProps {
  id: CardId
  /** col-span classes applied to the outer wrapper div (the grid item). */
  colSpanClass: string
  /** Card metadata shown in the reorder tile (icon + label). */
  meta: CardMeta
  /** When true, show the compact reorder tile instead of card content. */
  isReorderMode: boolean
  /** Index of this card in the current order (for up/down buttons). */
  index: number
  /** Total number of sortable cards (for disabling first/last arrows). */
  total: number
  /** Called when user taps the up arrow in reorder mode. */
  onMoveUp: () => void
  /** Called when user taps the down arrow in reorder mode. */
  onMoveDown: () => void
  /** Whether this card is hidden in normal mode (shown in reorder mode with indicator). */
  isHidden?: boolean
  /** Called when user taps the eye toggle in reorder mode. */
  onToggleHidden?: () => void
  children: ReactNode
}

export function SortableCard({
  id,
  colSpanClass,
  meta,
  isReorderMode,
  index,
  total,
  onMoveUp,
  onMoveDown,
  isHidden = false,
  onToggleHidden,
  children,
}: SortableCardProps) {
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
        // In normal mode use the provided col-span; reorder mode ignores it
        // (the flex column container controls layout instead of CSS grid).
        !isReorderMode && colSpanClass,
        // Dim the placeholder when DragOverlay is floating above it.
        isDragging && 'opacity-30',
      )}
    >
      {isReorderMode ? (
        <ReorderTile
          meta={meta}
          dragListeners={listeners}
          dragAttributes={attributes}
          isDragging={isDragging}
          isFirst={index === 0}
          isLast={index === total - 1}
          onMoveUp={onMoveUp}
          onMoveDown={onMoveDown}
          isHidden={isHidden}
          onToggleHidden={onToggleHidden}
        />
      ) : (
        children
      )}
    </div>
  )
}

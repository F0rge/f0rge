'use client'

/**
 * /customize/reorder — Reorder & visibility page.
 *
 * Lifted from the inline reorder mode that used to live in checkin-board.tsx.
 * Uses the same localStorage helpers (ht.cards-v2.order, ht.cards-v2.hidden)
 * and the same dnd-kit wiring (verticalListSortingStrategy — single-column list).
 */

import { useState, useCallback, useSyncExternalStore } from 'react'
import Link from 'next/link'
import {
  DndContext,
  DragOverlay,
  closestCenter,
  PointerSensor,
  TouchSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  arrayMove,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { ArrowLeft, Activity, Apple, BookOpen, Heart, Moon, Pill, RotateCcw, Zap } from 'lucide-react'
import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import {
  DEFAULT_CARD_ORDER,
  loadCardOrder,
  saveCardOrder,
  loadHiddenCards,
  saveHiddenCards,
  resetCardOrder,
  resetHiddenCards,
  type CardId,
} from '@/lib/checkin/card-order'
import { ReorderTile, type CardMeta } from '@/components/checkin/cards/reorder-tile'
import { TierBanner } from '@/components/customize/tier-banner'

// ── Card metadata (mirrors CARD_META in checkin-board.tsx) ───────────────────
// Defined at module scope to satisfy react-hooks/static-components rule.
const CARD_META: Record<CardId, CardMeta & { meta: string }> = {
  food:        { id: 'food',        icon: <Apple className="size-4" />,    label: 'Food & Diet',     meta: 'Photos + diet tags' },
  wellbeing:   { id: 'wellbeing',   icon: <Moon className="size-4" />,     label: 'Wellbeing',       meta: '4 scales' },
  gut:         { id: 'gut',         icon: <Activity className="size-4" />, label: 'Gut',             meta: '3 scales + Bristol' },
  supplements: { id: 'supplements', icon: <Pill className="size-4" />,     label: 'Supplements',     meta: 'Catalog' },
  symptoms:    { id: 'symptoms',    icon: <Zap className="size-4" />,      label: 'Symptoms',        meta: 'Custom' },
  trackers:    { id: 'trackers',    icon: <Heart className="size-4" />,    label: 'Daily trackers',  meta: 'Custom' },
  notes:       { id: 'notes',       icon: <BookOpen className="size-4" />, label: 'Notes',           meta: 'Free text' },
}

// ── Module-level stores for useSyncExternalStore ─────────────────────────────
// useSyncExternalStore is SSR-safe: getServerSnapshot runs on the server and
// during hydration (returning the stable default), getSnapshot runs on the client
// after hydration (returning the real localStorage value). React reconciles without
// a hydration mismatch. After hydration, any call to notify() triggers a re-read.
// 'use client' does NOT skip SSR — App Router still prerenders client components.

const cardOrderListeners = new Set<() => void>()
const hiddenCardsListeners = new Set<() => void>()

function notifyCardOrder() { cardOrderListeners.forEach((fn) => fn()) }
function notifyHiddenCards() { hiddenCardsListeners.forEach((fn) => fn()) }

function subscribeCardOrder(fn: () => void) {
  cardOrderListeners.add(fn)
  return () => { cardOrderListeners.delete(fn) }
}
function subscribeHiddenCards(fn: () => void) {
  hiddenCardsListeners.add(fn)
  return () => { hiddenCardsListeners.delete(fn) }
}

// ── SortableReorderRow ────────────────────────────────────────────────────────

interface SortableReorderRowProps {
  id: CardId
  index: number
  total: number
  isHidden: boolean
  onMoveUp: () => void
  onMoveDown: () => void
  onToggleHidden: () => void
}

function SortableReorderRow({
  id,
  index,
  total,
  isHidden,
  onMoveUp,
  onMoveDown,
  onToggleHidden,
}: SortableReorderRowProps) {
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
    <div ref={setNodeRef} style={style} className={isDragging ? 'opacity-30' : undefined}>
      <ReorderTile
        meta={CARD_META[id]}
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
    </div>
  )
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function ReorderPage() {
  // useSyncExternalStore: SSR-safe reads from localStorage.
  // getServerSnapshot returns the stable default (same on every server render).
  // getSnapshot returns the real localStorage value on the client.
  // Mutations call save* helpers then notify* to re-read from localStorage.
  const cardOrder = useSyncExternalStore(
    subscribeCardOrder,
    () => loadCardOrder(),
    () => [...DEFAULT_CARD_ORDER] as CardId[],
  )
  const hiddenCards = useSyncExternalStore(
    subscribeHiddenCards,
    () => loadHiddenCards(),
    () => [] as CardId[],
  )

  const [activeId, setActiveId] = useState<CardId | null>(null)

  // ── dnd-kit sensors ───────────────────────────────────────────────────────
  // Tiles have no inner interactive content, so no need for a distance constraint.
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 4 },
    }),
    useSensor(TouchSensor, {
      activationConstraint: { delay: 150, tolerance: 8 },
    }),
  )

  const handleDragStart = useCallback((event: DragStartEvent) => {
    setActiveId(event.active.id as CardId)
  }, [])

  const handleDragEnd = useCallback((event: DragEndEvent) => {
    setActiveId(null)
    const { active, over } = event
    if (!over || active.id === over.id) return
    const prev = loadCardOrder()
    const oldIndex = prev.indexOf(active.id as CardId)
    const newIndex = prev.indexOf(over.id as CardId)
    const next = arrayMove(prev, oldIndex, newIndex)
    saveCardOrder(next)
    notifyCardOrder()
  }, [])

  const handleDragCancel = useCallback(() => {
    setActiveId(null)
  }, [])

  // ── Arrow move handlers ───────────────────────────────────────────────────
  const handleMoveUp = useCallback((id: CardId) => {
    const prev = loadCardOrder()
    const idx = prev.indexOf(id)
    if (idx <= 0) return
    const next = arrayMove(prev, idx, idx - 1)
    saveCardOrder(next)
    notifyCardOrder()
  }, [])

  const handleMoveDown = useCallback((id: CardId) => {
    const prev = loadCardOrder()
    const idx = prev.indexOf(id)
    if (idx < 0 || idx >= prev.length - 1) return
    const next = arrayMove(prev, idx, idx + 1)
    saveCardOrder(next)
    notifyCardOrder()
  }, [])

  // ── Visibility toggle ─────────────────────────────────────────────────────
  const handleToggleHidden = useCallback((id: CardId) => {
    const prev = loadHiddenCards()
    const next = prev.includes(id) ? prev.filter((h) => h !== id) : [...prev, id]
    saveHiddenCards(next)
    notifyHiddenCards()
  }, [])

  // ── Reset ─────────────────────────────────────────────────────────────────
  const handleReset = useCallback(() => {
    resetCardOrder()
    resetHiddenCards()
    notifyCardOrder()
    notifyHiddenCards()
  }, [])

  return (
    <div className="mx-auto w-full max-w-lg p-4">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <Link
          href="/customize"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Customize
        </Link>
        <button
          type="button"
          onClick={handleReset}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
          aria-label="Reset to default order"
        >
          <RotateCcw className="size-3.5" />
          Reset
        </button>
      </div>

      <div className="mb-4">
        <h1 className="text-xl font-semibold tracking-tight">Reorder &amp; visibility</h1>
      </div>

      <TierBanner tier="core">
        Drag to reorder. Toggle the eye icon to show or hide a section on your daily check-in.
        Changes take effect immediately — no save button needed.
      </TierBanner>

      {/* Sortable list */}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
        onDragCancel={handleDragCancel}
      >
        <SortableContext items={cardOrder} strategy={verticalListSortingStrategy}>
          <div className="flex flex-col gap-2">
            {cardOrder.map((id, index) => (
              <SortableReorderRow
                key={id}
                id={id}
                index={index}
                total={cardOrder.length}
                isHidden={hiddenCards.includes(id)}
                onMoveUp={() => handleMoveUp(id)}
                onMoveDown={() => handleMoveDown(id)}
                onToggleHidden={() => handleToggleHidden(id)}
              />
            ))}
          </div>
        </SortableContext>

        {/* DragOverlay — uniform tile, no width capture needed (single-column list) */}
        <DragOverlay>
          {activeId !== null ? (
            <ReorderTile
              meta={CARD_META[activeId]}
              dragListeners={undefined}
              isDragging={true}
              isFirst={false}
              isLast={false}
              onMoveUp={() => {}}
              onMoveDown={() => {}}
            />
          ) : null}
        </DragOverlay>
      </DndContext>
    </div>
  )
}

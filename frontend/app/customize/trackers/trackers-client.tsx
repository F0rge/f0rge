'use client'

/**
 * /customize/trackers — full client UI for managing custom trackers.
 *
 * Loaded via next/dynamic({ ssr: false }) from page.tsx.
 * Seeded trackers (is_seed: true) are excluded from both active and archived lists.
 */

import { useState, useCallback } from 'react'
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
  useSortable,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import {
  ArrowLeft,
  ChevronDown,
  GripVertical,
  Pencil,
  Plus,
  Undo2,
  Trash2,
} from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { TierBanner } from '@/components/customize/tier-banner'
import { RowItem } from '@/components/customize/row-item'
import { TrackerFormModal } from '@/components/customize/tracker-form-modal'
import { useTrackers, useUpdateTracker, useReorderTrackers } from '@/lib/api/hooks'
import { ICON_COMPONENT_MAP } from '@/components/checkin/cards/components/IconPicker'
import type { Tracker } from '@/lib/api/types'

// ── Sortable row ──────────────────────────────────────────────────────────────
// Defined at module scope to satisfy react-hooks/static-components rule.

interface SortableTrackerRowProps {
  tracker: Tracker
  onEdit: (tracker: Tracker) => void
  onArchive: (tracker: Tracker) => void
}

function SortableTrackerRow({ tracker, onEdit, onArchive }: SortableTrackerRowProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: tracker.id })

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
          IconComponent ? (
            <IconComponent className="size-4 text-muted-foreground" />
          ) : undefined
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

// ── Ghost row (DragOverlay) ───────────────────────────────────────────────────

interface GhostRowProps {
  tracker: Tracker
}

function GhostRow({ tracker }: GhostRowProps) {
  const IconComponent = tracker.icon ? ICON_COMPONENT_MAP[tracker.icon] : null

  return (
    <RowItem
      dragHandle={
        <span className="text-muted-foreground/40">
          <GripVertical className="size-4" />
        </span>
      }
      icon={
        IconComponent ? (
          <IconComponent className="size-4 text-muted-foreground" />
        ) : undefined
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

// ── Page ─────────────────────────────────────────────────────────────────────

export default function TrackersClient() {
  const { data: allTrackers = [] } = useTrackers(true)
  const updateTracker = useUpdateTracker()
  const reorderTrackers = useReorderTrackers()

  // Exclude seeded trackers from both lists
  const active = allTrackers
    .filter((t) => !t.archived && !t.is_seed)
    .sort((a, b) => a.position - b.position || a.name.localeCompare(b.name))

  const archived = allTrackers.filter((t) => t.archived && !t.is_seed)

  // Modal state
  const [modalOpen, setModalOpen] = useState(false)
  const [editingTracker, setEditingTracker] = useState<Tracker | undefined>(undefined)

  // Archived section toggle
  const [archivedOpen, setArchivedOpen] = useState(false)

  // dnd-kit drag state (track active id + initial width so DragOverlay matches the source row)
  const [activeId, setActiveId] = useState<number | null>(null)
  const [dragOverlayWidth, setDragOverlayWidth] = useState<number | undefined>(undefined)
  const activeTracker = active.find((t) => t.id === activeId) ?? null

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 8 } }),
  )

  const handleDragStart = useCallback((event: DragStartEvent) => {
    setActiveId(event.active.id as number)
    // Capture the source row's rendered width so the overlay doesn't collapse
    // when it renders outside the parent list (see dnd_kit_grid_drag_reorder.md).
    const rect = event.active.rect.current.initial
    setDragOverlayWidth(rect ? rect.width : undefined)
  }, [])

  function handleDragEnd(event: DragEndEvent) {
    setActiveId(null)
    const { active, over } = event
    if (!over || active.id === over.id) return

    const activeList = allTrackers
      .filter((t) => !t.archived && !t.is_seed)
      .sort((a, b) => a.position - b.position || a.name.localeCompare(b.name))

    const oldIdx = activeList.findIndex((t) => t.id === active.id)
    const newIdx = activeList.findIndex((t) => t.id === over.id)
    if (oldIdx === -1 || newIdx === -1) return

    const reordered = arrayMove(activeList, oldIdx, newIdx)
    reorderTrackers.mutate(
      reordered.map((t) => t.id),
      { onError: () => toast.error('Failed to reorder trackers') },
    )
  }

  const handleDragCancel = useCallback(() => {
    setActiveId(null)
  }, [])

  function handleOpenCreate() {
    setEditingTracker(undefined)
    setModalOpen(true)
  }

  function handleEdit(tracker: Tracker) {
    setEditingTracker(tracker)
    setModalOpen(true)
  }

  function handleArchive(tracker: Tracker) {
    updateTracker.mutate(
      { id: tracker.id, data: { archived: true } },
      { onError: () => toast.error(`Failed to archive "${tracker.name}"`) },
    )
  }

  function handleRestore(tracker: Tracker) {
    updateTracker.mutate(
      { id: tracker.id, data: { archived: false } },
      { onError: () => toast.error(`Failed to restore "${tracker.name}"`) },
    )
  }

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
        <Button
          variant="ghost"
          size="sm"
          className="gap-1.5 text-xs"
          onClick={handleOpenCreate}
        >
          <Plus className="size-3.5" />
          New tracker
        </Button>
      </div>

      <div className="mb-4">
        <h1 className="text-xl font-semibold tracking-tight">Custom trackers</h1>
      </div>

      <TierBanner tier="custom">
        Add, edit, archive, and reorder your personal trackers. Drag rows to set the
        order on your daily check-in. Seeded trackers (Alcohol, Caffeine, etc.) are
        managed separately.
      </TierBanner>

      {/* Active list */}
      {active.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          No custom trackers yet.{' '}
          <button
            type="button"
            className="underline underline-offset-2 hover:text-foreground transition-colors"
            onClick={handleOpenCreate}
          >
            Add one
          </button>
          .
        </p>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
          onDragCancel={handleDragCancel}
        >
          <SortableContext
            items={active.map((t) => t.id)}
            strategy={verticalListSortingStrategy}
          >
            <div className="rounded-lg border border-border bg-card">
              {active.map((tracker) => (
                <SortableTrackerRow
                  key={tracker.id}
                  tracker={tracker}
                  onEdit={handleEdit}
                  onArchive={handleArchive}
                />
              ))}
            </div>
          </SortableContext>

          <DragOverlay>
            {activeTracker !== null ? (
              <div style={{ width: dragOverlayWidth }}>
                <GhostRow tracker={activeTracker} />
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      )}

      {/* Archived collapsible */}
      {archived.length > 0 && (
        <div className="mt-6">
          <button
            type="button"
            onClick={() => setArchivedOpen((v) => !v)}
            className="flex w-full items-center justify-between text-xs text-muted-foreground
              hover:text-foreground transition-colors py-2"
          >
            <span className="font-semibold uppercase tracking-wider">
              Archived ({archived.length})
            </span>
            <ChevronDown
              className={`size-4 transition-transform ${archivedOpen ? 'rotate-180' : ''}`}
            />
          </button>

          {archivedOpen && (
            <div className="mt-1 rounded-lg border border-border bg-muted/30">
              {archived.map((tracker) => {
                const IconComponent = tracker.icon ? ICON_COMPONENT_MAP[tracker.icon] : null
                return (
                  <RowItem
                    key={tracker.id}
                    icon={
                      IconComponent ? (
                        <IconComponent className="size-4 text-muted-foreground" />
                      ) : undefined
                    }
                    label={tracker.name}
                    meta={
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                        {tracker.kind}
                        {tracker.unit ? ` · ${tracker.unit}` : ''}
                      </span>
                    }
                    actions={
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-8 text-muted-foreground hover:text-foreground"
                        aria-label={`Restore ${tracker.name}`}
                        onClick={() => handleRestore(tracker)}
                      >
                        <Undo2 className="size-3.5" />
                      </Button>
                    }
                    dimmed
                  />
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* key resets useState initializers when switching between create/edit mode */}
      <TrackerFormModal
        key={editingTracker?.id ?? 'new'}
        open={modalOpen}
        onOpenChange={setModalOpen}
        tracker={editingTracker}
        trackerCount={active.length}
      />
    </div>
  )
}

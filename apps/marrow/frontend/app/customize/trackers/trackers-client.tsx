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
} from '@dnd-kit/sortable'
import { ArrowLeft, Plus } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@f0rge/ui'
import { TierBanner } from '@/components/customize/tier-banner'
import { TrackerFormModal } from '@/components/customize/tracker-form-modal'
import { PageShell } from '@/components/layout/page-shell'
import { PageHeader } from '@/components/layout/page-header'
import {
  SortableTrackerRow,
  GhostRow,
} from '@/components/customize/sortable-tracker-row'
import { ArchivedTrackersList } from '@/components/customize/archived-trackers-list'
import { useTrackers, useUpdateTracker, useReorderTrackers } from '@/lib/api/hooks'
import type { Tracker } from '@/lib/api/types'

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
    <PageShell>
      <PageHeader
        className="mb-4"
        leading={
          <Link
            href="/customize"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
            Customize
          </Link>
        }
        title="Custom trackers"
        actions={
          <Button
            variant="ghost"
            size="sm"
            className="gap-1.5 text-xs"
            onClick={handleOpenCreate}
          >
            <Plus className="size-3.5" />
            New tracker
          </Button>
        }
      />

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

      <ArchivedTrackersList archived={archived} onRestore={handleRestore} />

      {/* key resets useState initializers when switching between create/edit mode */}
      <TrackerFormModal
        key={editingTracker?.id ?? 'new'}
        open={modalOpen}
        onOpenChange={setModalOpen}
        tracker={editingTracker}
        trackerCount={active.length}
      />
    </PageShell>
  )
}

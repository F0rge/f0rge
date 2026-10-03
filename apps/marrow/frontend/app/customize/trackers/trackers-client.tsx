'use client'

/**
 * /customize/trackers — full client UI for managing custom trackers.
 *
 * Loaded via next/dynamic({ ssr: false }) from page.tsx.
 * Seeded trackers (is_seed: true) are excluded from both active and archived lists.
 */

import { useState, useEffect, useMemo } from 'react'
import Link from 'next/link'
import { ArrowLeft, Plus } from 'lucide-react'
import { toast } from 'sonner'
import { Button, Sortable } from '@f0rge/ui'
import { TierBanner } from '@/components/customize/tier-banner'
import { TrackerFormModal } from '@/components/customize/tracker-form-modal'
import { PageShell } from '@/components/layout/page-shell'
import { PageHeader } from '@/components/layout/page-header'
import { SortableTrackerRow } from '@/components/customize/sortable-tracker-row'
import { ArchivedTrackersList } from '@/components/customize/archived-trackers-list'
import { useTrackers, useUpdateTracker, useReorderTrackers } from '@/lib/api/hooks'
import type { Tracker } from '@/lib/api/types'

export default function TrackersClient() {
  const { data: allTrackers = [] } = useTrackers(true)
  const updateTracker = useUpdateTracker()
  const reorderTrackers = useReorderTrackers()

  // Exclude seeded trackers from both lists
  const active = useMemo(
    () =>
      allTrackers
        .filter((t) => !t.archived && !t.is_seed)
        .sort((a, b) => a.position - b.position || a.name.localeCompare(b.name)),
    [allTrackers],
  )

  const archived = allTrackers.filter((t) => t.archived && !t.is_seed)

  const [orderedActive, setOrderedActive] = useState(active)
  useEffect(() => {
    setOrderedActive(active)
  }, [active])

  // Modal state
  const [modalOpen, setModalOpen] = useState(false)
  const [editingTracker, setEditingTracker] = useState<Tracker | undefined>(undefined)

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
        <Sortable
          value={orderedActive}
          onValueChange={setOrderedActive}
          getItemValue={(t) => String(t.id)}
          onValueCommit={(reordered) => {
            reorderTrackers.mutate(
              reordered.map((t) => t.id),
              { onError: () => toast.error('Failed to reorder trackers') },
            )
          }}
          className="overflow-hidden rounded-lg border border-border bg-card"
        >
          {orderedActive.map((tracker) => (
            <SortableTrackerRow
              key={tracker.id}
              tracker={tracker}
              onEdit={handleEdit}
              onArchive={handleArchive}
            />
          ))}
        </Sortable>
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

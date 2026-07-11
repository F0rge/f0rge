'use client'

/**
 * /customize/symptoms — full client UI for managing custom symptoms.
 *
 * Loaded via next/dynamic({ ssr: false }) from page.tsx.
 * All symptoms are user-created (no is_seed concept).
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
import { SymptomFormModal } from '@/components/customize/symptom-form-modal'
import { PageShell } from '@/components/layout/page-shell'
import { PageHeader } from '@/components/layout/page-header'
import {
  SortableSymptomRow,
  GhostRow,
} from '@/components/customize/sortable-symptom-row'
import { ArchivedSymptomsList } from '@/components/customize/archived-symptoms-list'
import {
  useSymptomCatalog,
  useUpdateSymptomCatalogItem,
  useReorderSymptomCatalog,
} from '@/lib/api/hooks'
import type { SymptomCatalogItem } from '@/lib/api/types'

export default function SymptomsClient() {
  const { data: allSymptoms = [] } = useSymptomCatalog(true)
  const updateSymptom = useUpdateSymptomCatalogItem()
  const reorderSymptoms = useReorderSymptomCatalog()

  const active = allSymptoms
    .filter((s) => !s.archived)
    .sort((a, b) => a.sort_order - b.sort_order)

  const archived = allSymptoms.filter((s) => s.archived)

  // Modal state
  const [modalOpen, setModalOpen] = useState(false)
  const [editingSymptom, setEditingSymptom] = useState<SymptomCatalogItem | undefined>(undefined)

  // dnd-kit drag state
  const [activeId, setActiveId] = useState<string | null>(null)
  const [dragOverlayWidth, setDragOverlayWidth] = useState<number | undefined>(undefined)
  const activeSymptom = active.find((s) => s.key === activeId) ?? null

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 8 } }),
  )

  const handleDragStart = useCallback((event: DragStartEvent) => {
    setActiveId(event.active.id as string)
    const rect = event.active.rect.current.initial
    setDragOverlayWidth(rect ? rect.width : undefined)
  }, [])

  function handleDragEnd(event: DragEndEvent) {
    setActiveId(null)
    const { active, over } = event
    if (!over || active.id === over.id) return

    const activeList = allSymptoms
      .filter((s) => !s.archived)
      .sort((a, b) => a.sort_order - b.sort_order)

    const oldIdx = activeList.findIndex((s) => s.key === active.id)
    const newIdx = activeList.findIndex((s) => s.key === over.id)
    if (oldIdx === -1 || newIdx === -1) return

    const reordered = arrayMove(activeList, oldIdx, newIdx)
    reorderSymptoms.mutate(
      reordered.map((s) => s.key),
      { onError: () => toast.error('Failed to reorder symptoms') },
    )
  }

  const handleDragCancel = useCallback(() => {
    setActiveId(null)
  }, [])

  function handleOpenCreate() {
    setEditingSymptom(undefined)
    setModalOpen(true)
  }

  function handleEdit(symptom: SymptomCatalogItem) {
    setEditingSymptom(symptom)
    setModalOpen(true)
  }

  function handleArchive(symptom: SymptomCatalogItem) {
    updateSymptom.mutate(
      { key: symptom.key, data: { archived: true } },
      { onError: () => toast.error(`Failed to archive "${symptom.label}"`) },
    )
  }

  function handleRestore(symptom: SymptomCatalogItem) {
    updateSymptom.mutate(
      { key: symptom.key, data: { archived: false } },
      { onError: () => toast.error(`Failed to restore "${symptom.label}"`) },
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
        title="Custom symptoms"
        actions={
          <Button
            variant="ghost"
            size="sm"
            className="gap-1.5 text-xs"
            onClick={handleOpenCreate}
          >
            <Plus className="size-3.5" />
            New symptom
          </Button>
        }
      />

      <TierBanner tier="custom">
        Add, edit, archive, and reorder your personal symptom list. Drag rows to set the
        order they appear on your daily check-in.
      </TierBanner>

      {/* Active list */}
      {active.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          No custom symptoms yet.{' '}
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
            items={active.map((s) => s.key)}
            strategy={verticalListSortingStrategy}
          >
            <div className="rounded-lg border border-border bg-card">
              {active.map((symptom) => (
                <SortableSymptomRow
                  key={symptom.key}
                  symptom={symptom}
                  onEdit={handleEdit}
                  onArchive={handleArchive}
                />
              ))}
            </div>
          </SortableContext>

          <DragOverlay>
            {activeSymptom !== null ? (
              <div style={{ width: dragOverlayWidth }}>
                <GhostRow symptom={activeSymptom} />
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      )}

      <ArchivedSymptomsList archived={archived} onRestore={handleRestore} />

      {/* key resets useState initializers when switching between create/edit mode */}
      <SymptomFormModal
        key={editingSymptom?.key ?? 'new'}
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        symptom={editingSymptom}
      />
    </PageShell>
  )
}

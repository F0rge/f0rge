'use client'

/**
 * /customize/symptoms — full client UI for managing custom symptoms.
 *
 * Loaded via next/dynamic({ ssr: false }) from page.tsx.
 * All symptoms are user-created (no is_seed concept).
 */

import { useState, useEffect, useMemo } from 'react'
import Link from 'next/link'
import { ArrowLeft, Plus } from 'lucide-react'
import { toast } from 'sonner'
import { Button, Sortable } from '@f0rge/ui'
import { TierBanner } from '@/components/customize/tier-banner'
import { SymptomFormModal } from '@/components/customize/symptom-form-modal'
import { PageShell } from '@/components/layout/page-shell'
import { PageHeader } from '@/components/layout/page-header'
import { SortableSymptomRow } from '@/components/customize/sortable-symptom-row'
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

  const active = useMemo(
    () =>
      allSymptoms
        .filter((s) => !s.archived)
        .sort((a, b) => a.sort_order - b.sort_order),
    [allSymptoms],
  )

  const archived = allSymptoms.filter((s) => s.archived)

  const [orderedActive, setOrderedActive] = useState(active)
  useEffect(() => {
    setOrderedActive(active)
  }, [active])

  // Modal state
  const [modalOpen, setModalOpen] = useState(false)
  const [editingSymptom, setEditingSymptom] = useState<SymptomCatalogItem | undefined>(undefined)

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
        <Sortable
          value={orderedActive}
          onValueChange={setOrderedActive}
          getItemValue={(s) => s.key}
          onValueCommit={(reordered) => {
            reorderSymptoms.mutate(
              reordered.map((s) => s.key),
              { onError: () => toast.error('Failed to reorder symptoms') },
            )
          }}
          className="overflow-hidden rounded-lg border border-border bg-card"
        >
          {orderedActive.map((symptom) => (
            <SortableSymptomRow
              key={symptom.key}
              symptom={symptom}
              onEdit={handleEdit}
              onArchive={handleArchive}
            />
          ))}
        </Sortable>
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

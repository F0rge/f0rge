'use client'

import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'
import { toast } from 'sonner'
import { TierBanner } from '@/components/customize/tier-banner'
import { CatalogSection } from '@/components/customize/catalog-section'
import { PageShell } from '@/components/layout/page-shell'
import { PageHeader } from '@/components/layout/page-header'
import {
  useSupplementCatalog,
  useUpdateSupplementCatalogItem,
  useAddSupplementCatalogItem,
  useMedicationCatalog,
  useUpdateMedicationCatalogItem,
  useAddMedicationCatalogItem,
  useDietTagCatalog,
  useUpdateDietTagCatalogItem,
  useCatalogSuggestions,
} from '@/lib/api/hooks'

export default function CatalogsClient() {
  const {
    data: supplements = [],
    isLoading: supplementsLoading,
    isError: supplementsError,
  } = useSupplementCatalog(true)
  const {
    data: medications = [],
    isLoading: medicationsLoading,
    isError: medicationsError,
  } = useMedicationCatalog(true)
  const {
    data: dietTags = [],
    isLoading: dietTagsLoading,
    isError: dietTagsError,
  } = useDietTagCatalog(true)
  const { data: suggestions } = useCatalogSuggestions()

  const updateSupplement = useUpdateSupplementCatalogItem()
  const addSupplement = useAddSupplementCatalogItem()
  const updateMedication = useUpdateMedicationCatalogItem()
  const addMedication = useAddMedicationCatalogItem()
  const updateDietTag = useUpdateDietTagCatalogItem()

  const isLoading = supplementsLoading || medicationsLoading || dietTagsLoading
  const hasError = supplementsError || medicationsError || dietTagsError

  function handleToggleSupplement(key: string, currentArchived: boolean) {
    updateSupplement.mutate(
      { key, data: { archived: !currentArchived } },
      { onError: () => toast.error('Failed to update supplement') },
    )
  }

  function handleToggleMedication(key: string, currentArchived: boolean) {
    updateMedication.mutate(
      { key, data: { archived: !currentArchived } },
      { onError: () => toast.error('Failed to update medication') },
    )
  }

  function handleToggleDietTag(key: string, currentArchived: boolean) {
    updateDietTag.mutate(
      { key, data: { archived: !currentArchived } },
      { onError: () => toast.error('Failed to update diet tag') },
    )
  }

  function handleAddSupplement(key: string, label: string) {
    addSupplement.mutate(
      { key, label },
      {
        onSuccess: () => toast.success(`Added ${label}`),
        onError: () => toast.error('Failed to add supplement'),
      },
    )
  }

  function handleAddMedication(key: string, label: string) {
    addMedication.mutate(
      { key, label },
      {
        onSuccess: () => toast.success(`Added ${label}`),
        onError: () => toast.error('Failed to add medication'),
      },
    )
  }

  const supplementSuggestions = [
    ...(suggestions?.supplements ?? []),
    ...(suggestions?.bulk_supplements ?? []),
  ]
  const medicationSuggestions = [
    ...(suggestions?.medications ?? []),
    ...(suggestions?.bulk_medications ?? []),
  ]

  const activeSupplements = supplements.filter((s) => !s.archived).length
  const activeMedications = medications.filter((m) => !m.archived).length
  const activeDietTags = dietTags.filter((d) => !d.archived).length

  return (
    <PageShell>
      <PageHeader
        leading={
          <Link
            href="/customize"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
            Customize
          </Link>
        }
        title="Catalogs"
      />

      <TierBanner tier="catalog">
        Pick which supplements, medications, and diet tags appear on your daily
        check-in. Items can be archived (hidden from the picker) but not deleted —
        your historical entries keep their tags.
      </TierBanner>

      {hasError ? (
        <div className="mt-4 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          Couldn&apos;t load catalogs. Refresh the page to try again.
        </div>
      ) : isLoading ? (
        <div className="mt-4 space-y-3">
          <div className="h-5 w-28 animate-pulse rounded bg-muted" />
          <div className="h-10 w-full animate-pulse rounded bg-muted" />
          <div className="h-5 w-28 animate-pulse rounded bg-muted" />
          <div className="h-10 w-full animate-pulse rounded bg-muted" />
        </div>
      ) : (
        <div className="mt-4 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <CatalogSection
            title="Supplements"
            items={supplements}
            suggestions={supplementSuggestions}
            onToggleArchive={handleToggleSupplement}
            onAddSuggestion={handleAddSupplement}
            selectedCount={activeSupplements}
            totalCount={supplements.length}
          />

          <CatalogSection
            title="Medications"
            items={medications}
            suggestions={medicationSuggestions}
            onToggleArchive={handleToggleMedication}
            onAddSuggestion={handleAddMedication}
            selectedCount={activeMedications}
            totalCount={medications.length}
          />

          <div className="lg:col-span-2">
            <CatalogSection
              title="Diet tags"
              items={dietTags}
              onToggleArchive={handleToggleDietTag}
              selectedCount={activeDietTags}
              totalCount={dietTags.length}
            />
          </div>
        </div>
      )}
    </PageShell>
  )
}

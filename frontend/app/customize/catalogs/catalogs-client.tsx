'use client'

import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'
import { toast } from 'sonner'
import { TierBanner } from '@/components/customize/tier-banner'
import { CatalogSection } from '@/components/customize/catalog-section'
import {
  useSupplementCatalog,
  useUpdateSupplementCatalogItem,
  useDietTagCatalog,
  useUpdateDietTagCatalogItem,
} from '@/lib/api/hooks'

export default function CatalogsClient() {
  const {
    data: supplements = [],
    isLoading: supplementsLoading,
    isError: supplementsError,
  } = useSupplementCatalog(true)
  const {
    data: dietTags = [],
    isLoading: dietTagsLoading,
    isError: dietTagsError,
  } = useDietTagCatalog(true)

  const updateSupplement = useUpdateSupplementCatalogItem()
  const updateDietTag = useUpdateDietTagCatalogItem()

  const isLoading = supplementsLoading || dietTagsLoading
  const hasError = supplementsError || dietTagsError

  function handleToggleSupplement(key: string, currentArchived: boolean) {
    updateSupplement.mutate(
      { key, data: { archived: !currentArchived } },
      { onError: () => toast.error('Failed to update supplement') },
    )
  }

  function handleToggleDietTag(key: string, currentArchived: boolean) {
    updateDietTag.mutate(
      { key, data: { archived: !currentArchived } },
      { onError: () => toast.error('Failed to update diet tag') },
    )
  }

  const activeSupplements = supplements.filter((s) => !s.archived).length
  const activeDietTags = dietTags.filter((d) => !d.archived).length

  return (
    <div className="mx-auto w-full max-w-lg p-4">
      {/* Header */}
      <div className="mb-6">
        <Link
          href="/customize"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Customize
        </Link>
        <h1 className="mt-3 text-xl font-semibold tracking-tight">Catalogs</h1>
      </div>

      <TierBanner tier="catalog">
        Pick which supplements and diet tags appear on your daily check-in. Items
        can be archived (hidden from the picker) but not deleted — your historical
        entries keep their tags.
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
        <>
          <CatalogSection
            title="Supplements"
            items={supplements}
            onToggleArchive={handleToggleSupplement}
            selectedCount={activeSupplements}
            totalCount={supplements.length}
          />

          <CatalogSection
            title="Diet tags"
            items={dietTags}
            onToggleArchive={handleToggleDietTag}
            selectedCount={activeDietTags}
            totalCount={dietTags.length}
          />
        </>
      )}
    </div>
  )
}

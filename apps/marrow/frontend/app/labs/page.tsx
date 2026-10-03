'use client'

import { useState } from 'react'
import { Loader2, List, FlaskConical, Upload, Plus } from 'lucide-react'
import { useLabs } from '@/lib/api/hooks'
import { LG_DESKTOP_QUERY, useMediaQuery } from '@f0rge/ui'
import { LabCard } from '@/components/labs/lab-card'
import { LabDetailPanel } from '@/components/labs/lab-detail-panel'
import { LabDetailInline } from '@/components/labs/lab-detail-inline'
import { LabFormDialog } from '@/components/labs/lab-form-dialog'
import { LabUploadDialog } from '@/components/labs/lab-upload-dialog'
import { MarkerList } from '@/components/labs/marker-list'
import { EmptyMark } from '@/components/shared/color-artifact'
import { PageShell } from '@/components/layout/page-shell'
import { PageHeader } from '@/components/layout/page-header'
import {
  Button,
  ButtonGroup,
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
  FetchError,
  ToggleGroup,
  ToggleGroupItem,
} from '@f0rge/ui'
import type { Lab } from '@/lib/api/types'

type View = 'by-lab' | 'by-marker'

export default function LabsPage() {
  const { data: labs, isLoading, isError, refetch } = useLabs()
  const isDesktop = useMediaQuery(LG_DESKTOP_QUERY)
  const [view, setView] = useState<View>('by-lab')
  const [addOpen, setAddOpen] = useState(false)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [selectedLab, setSelectedLab] = useState<Lab | null>(null)

  return (
    <PageShell>
      <PageHeader
        layout="responsive"
        data-tour="labs-page"
        title="Labs"
        actions={
          <div className="flex items-center gap-1">
            <ToggleGroup
              spacing={0}
              variant="outline"
              value={[view]}
              onValueChange={(next) => {
                const picked = next[0]
                if (picked === 'by-lab' || picked === 'by-marker') setView(picked)
              }}
              className="rounded-lg border border-border p-0.5"
            >
              <ToggleGroupItem value="by-lab" size="sm" className="gap-1 px-2.5 text-xs">
                <List className="size-3.5" />
                By Lab
              </ToggleGroupItem>
              <ToggleGroupItem value="by-marker" size="sm" className="gap-1 px-2.5 text-xs">
                <FlaskConical className="size-3.5" />
                By Marker
              </ToggleGroupItem>
            </ToggleGroup>

            <ButtonGroup>
              <Button type="button" variant="ghost" size="sm" onClick={() => setUploadOpen(true)}>
                <Upload className="size-3.5" />
                Upload
              </Button>
              <Button type="button" variant="ghost" size="sm" onClick={() => setAddOpen(true)}>
                <Plus className="size-4" />
                Add
              </Button>
            </ButtonGroup>
          </div>
        }
      />

      {view === 'by-lab' && (
        <>
          {isLoading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="size-6 animate-spin text-muted-foreground" />
            </div>
          )}

          {isError && (
            <FetchError message="Failed to load labs." onRetry={() => refetch()} />
          )}

          {!isLoading && !isError && (!labs || labs.length === 0) && (
            <Empty className="border-border py-16">
              <EmptyHeader>
                <EmptyMedia>
                  <EmptyMark />
                </EmptyMedia>
                <EmptyTitle>No labs yet</EmptyTitle>
                <EmptyDescription>
                  Add lab results manually or upload a PDF/image for automatic extraction.
                </EmptyDescription>
              </EmptyHeader>
              <EmptyContent className="flex-row gap-2">
                <Button type="button" variant="outline" onClick={() => setUploadOpen(true)}>
                  Upload lab
                </Button>
                <Button type="button" onClick={() => setAddOpen(true)}>
                  Add manually
                </Button>
              </EmptyContent>
            </Empty>
          )}

          {!isLoading && !isError && labs && labs.length > 0 && (
            <div className="grid grid-cols-12 gap-6">
              <div className="col-span-12 space-y-2 lg:col-span-5">
                {labs.map((lab) => (
                  <LabCard
                    key={lab.id}
                    lab={lab}
                    selected={selectedLab?.id === lab.id}
                    onClick={() => setSelectedLab(lab)}
                  />
                ))}
              </div>

              <div className="relative hidden lg:col-span-7 lg:block">
                {selectedLab ? (
                  <LabDetailInline
                    lab={selectedLab}
                    onClose={() => setSelectedLab(null)}
                  />
                ) : (
                  <div className="flex h-full min-h-[320px] items-center justify-center rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
                    Select a lab to view marker details
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}

      {view === 'by-marker' && <MarkerList />}

      <LabFormDialog
        key={addOpen ? 'add-open' : 'add-closed'}
        open={addOpen}
        onOpenChange={setAddOpen}
      />

      <LabUploadDialog open={uploadOpen} onOpenChange={setUploadOpen} />

      <LabDetailPanel
        lab={selectedLab}
        open={!!selectedLab && !isDesktop}
        onOpenChange={(o) => { if (!o) setSelectedLab(null) }}
      />
    </PageShell>
  )
}

'use client'

import { useState } from 'react'
import { Loader2, Plus, List, BarChart3, Upload } from 'lucide-react'
import { useTreatments } from '@/lib/api/hooks'
import { TreatmentCard } from '@/components/treatments/treatment-card'
import { TreatmentFormDialog } from '@/components/treatments/treatment-form-dialog'
import { TreatmentUploadDialog } from '@/components/treatments/treatment-upload-dialog'
import { DiscontinueDialog } from '@/components/treatments/discontinue-dialog'
import { TreatmentTimeline } from '@/components/treatments/treatment-timeline'
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
import { EmptyMark } from '@/components/shared/color-artifact'
import type { Treatment } from '@/lib/api/types'
import { groupTreatments } from '@/components/treatments/group-treatments'

export default function TreatmentsPage() {
  const { data: treatments, isLoading, isError, refetch } = useTreatments()
  const [view, setView] = useState<'list' | 'timeline'>('list')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [editTreatment, setEditTreatment] = useState<Treatment | null>(null)
  const [dialogKey, setDialogKey] = useState(0)
  const [discontinueTarget, setDiscontinueTarget] = useState<Treatment | null>(null)
  const [discontinueOpen, setDiscontinueOpen] = useState(false)
  const [discontinueKey, setDiscontinueKey] = useState(0)

  function openAdd() {
    setEditTreatment(null)
    setDialogKey((k) => k + 1)
    setDialogOpen(true)
  }

  function openEdit(t: Treatment) {
    setEditTreatment(t)
    setDialogKey((k) => k + 1)
    setDialogOpen(true)
  }

  function openDiscontinue(t: Treatment) {
    setDiscontinueTarget(t)
    setDiscontinueKey((k) => k + 1)
    setDiscontinueOpen(true)
  }

  return (
    <PageShell>
      <PageHeader
        layout="responsive"
        data-tour="treatments-page"
        title="Treatments"
        actions={
          <div className="flex items-center gap-1">
            <ToggleGroup
              spacing={0}
              variant="outline"
              value={[view]}
              onValueChange={(next) => {
                const picked = next[0]
                if (picked === 'list' || picked === 'timeline') setView(picked)
              }}
              className="rounded-lg border border-border p-0.5"
            >
              <ToggleGroupItem value="list" size="sm" className="gap-1 px-2.5 text-xs">
                <List className="size-3.5" />
                List
              </ToggleGroupItem>
              <ToggleGroupItem value="timeline" size="sm" className="gap-1 px-2.5 text-xs">
                <BarChart3 className="size-3.5" />
                Timeline
              </ToggleGroupItem>
            </ToggleGroup>

            <ButtonGroup>
              <Button type="button" variant="ghost" size="sm" onClick={() => setUploadOpen(true)}>
                <Upload className="size-3.5" />
                Upload
              </Button>
              <Button type="button" variant="ghost" size="sm" onClick={openAdd}>
                <Plus className="size-4" />
                Add
              </Button>
            </ButtonGroup>
          </div>
        }
      />

      {isError ? (
        <FetchError message="Failed to load treatments." onRetry={() => refetch()} />
      ) : isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      ) : !treatments || treatments.length === 0 ? (
        <Empty className="border-border py-16">
          <EmptyHeader>
            <EmptyMedia>
              <EmptyMark />
            </EmptyMedia>
            <EmptyTitle>No treatments yet</EmptyTitle>
            <EmptyDescription>
              Track courses of antibiotics, antimicrobials, and other treatments.
            </EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            <Button type="button" onClick={openAdd}>Add treatment</Button>
          </EmptyContent>
        </Empty>
      ) : view === 'list' ? (
        <div className="space-y-5">
          {groupTreatments(treatments).map((section) => (
            <div key={section.label ?? '__ungrouped__'} className="space-y-2">
              {section.label && (
                <div className="flex items-center gap-2 px-1">
                  <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    {section.label}
                  </span>
                  <span className="text-xs text-muted-foreground/60">
                    {section.treatments.length}
                  </span>
                </div>
              )}
              <div className="grid grid-cols-12 gap-2">
                {section.treatments.map((t) => (
                  <div key={t.id} className="col-span-12 lg:col-span-6">
                    <TreatmentCard
                      treatment={t}
                      onClick={() => openEdit(t)}
                      onDiscontinue={() => openDiscontinue(t)}
                    />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <TreatmentTimeline treatments={treatments} onTreatmentClick={openEdit} />
      )}

      <TreatmentFormDialog
        key={dialogKey}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        treatment={editTreatment}
      />

      <TreatmentUploadDialog open={uploadOpen} onOpenChange={setUploadOpen} />

      {discontinueTarget && (
        <DiscontinueDialog
          key={discontinueKey}
          open={discontinueOpen}
          onOpenChange={setDiscontinueOpen}
          treatment={discontinueTarget}
        />
      )}
    </PageShell>
  )
}

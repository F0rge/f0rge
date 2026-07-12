'use client'

import { useState } from 'react'
import { Loader2, Plus, Pill, List, BarChart3, Upload } from 'lucide-react'
import { useTreatments } from '@/lib/api/hooks'
import { TreatmentCard } from '@/components/treatments/treatment-card'
import { TreatmentFormDialog } from '@/components/treatments/treatment-form-dialog'
import { TreatmentUploadDialog } from '@/components/treatments/treatment-upload-dialog'
import { DiscontinueDialog } from '@/components/treatments/discontinue-dialog'
import { TreatmentTimeline } from '@/components/treatments/treatment-timeline'
import { PageShell } from '@/components/layout/page-shell'
import { PageHeader } from '@/components/layout/page-header'
import { FetchError } from '@f0rge/ui'
import type { Treatment } from '@/lib/api/types'
import { cn } from '@f0rge/ui'
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
            <div className="flex rounded-lg border border-border">
              <button
                type="button"
                onClick={() => setView('list')}
                className={cn(
                  'flex items-center gap-1 rounded-l-lg px-2.5 py-1.5 text-xs font-medium transition-colors',
                  view === 'list'
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground',
                )}
              >
                <List className="size-3.5" />
                List
              </button>
              <button
                type="button"
                onClick={() => setView('timeline')}
                className={cn(
                  'flex items-center gap-1 rounded-r-lg px-2.5 py-1.5 text-xs font-medium transition-colors',
                  view === 'timeline'
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:text-foreground',
                )}
              >
                <BarChart3 className="size-3.5" />
                Timeline
              </button>
            </div>
            <button
              type="button"
              onClick={() => setUploadOpen(true)}
              className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium text-primary transition-colors hover:bg-primary/10"
            >
              <Upload className="size-3.5" />
              Upload
            </button>
            <button
              type="button"
              onClick={openAdd}
              className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm font-medium text-primary transition-colors hover:bg-primary/10"
            >
              <Plus className="size-4" />
              Add
            </button>
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
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <Pill className="mb-4 size-12 text-muted-foreground/40" />
          <h2 className="mb-1 text-lg font-semibold">No treatments yet</h2>
          <p className="mb-4 text-sm text-muted-foreground">
            Track courses of antibiotics, antimicrobials, and other treatments.
          </p>
          <button
            type="button"
            onClick={openAdd}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Add treatment
          </button>
        </div>
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

'use client'

import { useState } from 'react'
import { Loader2, Plus, Pill, List, BarChart3 } from 'lucide-react'
import { useTreatments } from '@/lib/api/hooks'
import { TreatmentCard } from '@/components/treatments/treatment-card'
import { TreatmentFormDialog } from '@/components/treatments/treatment-form-dialog'
import { TreatmentTimeline } from '@/components/treatments/treatment-timeline'
import type { Treatment } from '@/lib/api/types'
import { cn } from '@/lib/utils'

export default function TreatmentsPage() {
  const { data: treatments, isLoading } = useTreatments()
  const [view, setView] = useState<'list' | 'timeline'>('list')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editTreatment, setEditTreatment] = useState<Treatment | null>(null)

  function openAdd() {
    setEditTreatment(null)
    setDialogOpen(true)
  }

  function openEdit(t: Treatment) {
    setEditTreatment(t)
    setDialogOpen(true)
  }

  return (
    <div className="mx-auto w-full max-w-lg p-4">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold tracking-tight">Treatments</h1>
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
            onClick={openAdd}
            className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm font-medium text-primary transition-colors hover:bg-primary/10"
          >
            <Plus className="size-4" />
            Add
          </button>
        </div>
      </div>

      {isLoading ? (
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
        <div className="space-y-2">
          {treatments.map((t) => (
            <TreatmentCard key={t.id} treatment={t} onClick={() => openEdit(t)} />
          ))}
        </div>
      ) : (
        <TreatmentTimeline treatments={treatments} onTreatmentClick={openEdit} />
      )}

      <TreatmentFormDialog
        key={editTreatment?.id ?? 'add'}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        treatment={editTreatment}
      />
    </div>
  )
}

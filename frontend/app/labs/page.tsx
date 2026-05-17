'use client'

import { useState } from 'react'
import { Loader2, Microscope, List, FlaskConical, Upload, Plus } from 'lucide-react'
import { useLabs } from '@/lib/api/hooks'
import { LabCard } from '@/components/labs/lab-card'
import { LabDetailPanel } from '@/components/labs/lab-detail-panel'
import { LabFormDialog } from '@/components/labs/lab-form-dialog'
import { LabUploadDialog } from '@/components/labs/lab-upload-dialog'
import { MarkerList } from '@/components/labs/marker-list'
import { cn } from '@/lib/utils'
import type { Lab } from '@/lib/api/types'

type View = 'by-lab' | 'by-marker'

export default function LabsPage() {
  const { data: labs, isLoading, isError } = useLabs()
  const [view, setView] = useState<View>('by-lab')
  const [addOpen, setAddOpen] = useState(false)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [selectedLab, setSelectedLab] = useState<Lab | null>(null)

  return (
    <div className="mx-auto w-full max-w-lg p-4">
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h1 className="text-xl font-semibold tracking-tight">Labs</h1>

        <div className="flex items-center gap-1">
          <div className="flex rounded-lg border border-border">
            <button
              type="button"
              onClick={() => setView('by-lab')}
              className={cn(
                'flex items-center gap-1 rounded-l-lg px-2.5 py-1.5 text-xs font-medium transition-colors',
                view === 'by-lab'
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <List className="size-3.5" />
              By Lab
            </button>
            <button
              type="button"
              onClick={() => setView('by-marker')}
              className={cn(
                'flex items-center gap-1 rounded-r-lg px-2.5 py-1.5 text-xs font-medium transition-colors',
                view === 'by-marker'
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <FlaskConical className="size-3.5" />
              By Marker
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
            onClick={() => setAddOpen(true)}
            className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium text-primary transition-colors hover:bg-primary/10"
          >
            <Plus className="size-4" />
            Add
          </button>
        </div>
      </div>

      {view === 'by-lab' && (
        <>
          {isLoading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="size-6 animate-spin text-muted-foreground" />
            </div>
          )}

          {isError && (
            <p className="py-4 text-sm text-destructive">Failed to load labs.</p>
          )}

          {!isLoading && !isError && (!labs || labs.length === 0) && (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <Microscope className="mb-4 size-12 text-muted-foreground/40" />
              <h2 className="mb-1 text-lg font-semibold">No labs yet</h2>
              <p className="mb-4 text-sm text-muted-foreground">
                Add lab results manually or upload a PDF/image for automatic extraction.
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setUploadOpen(true)}
                  className="rounded-lg border border-primary px-4 py-2 text-sm font-medium text-primary transition-colors hover:bg-primary/10"
                >
                  Upload lab
                </button>
                <button
                  type="button"
                  onClick={() => setAddOpen(true)}
                  className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
                >
                  Add manually
                </button>
              </div>
            </div>
          )}

          {!isLoading && !isError && labs && labs.length > 0 && (
            <div className="space-y-2">
              {labs.map((lab) => (
                <LabCard
                  key={lab.id}
                  lab={lab}
                  onClick={() => setSelectedLab(lab)}
                />
              ))}
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
        open={!!selectedLab}
        onOpenChange={(o) => { if (!o) setSelectedLab(null) }}
      />
    </div>
  )
}

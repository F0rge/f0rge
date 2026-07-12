'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@f0rge/ui'
import { Button } from '@f0rge/ui'
import { Input } from '@f0rge/ui'
import { Label } from '@f0rge/ui'
import { Textarea } from '@f0rge/ui'
import { useCreateTreatment } from '@/lib/api/hooks'
import { handleMutationError } from '@f0rge/ui/api'
import { cn } from '@f0rge/ui'
import type { ExtractedTreatmentCandidate, TreatmentType } from '@/lib/api/types'

const TREATMENT_TYPES: { value: TreatmentType; label: string }[] = [
  { value: 'antibiotic', label: 'Antibiotic' },
  { value: 'antimicrobial', label: 'Antimicrobial' },
  { value: 'prescription', label: 'Prescription' },
  { value: 'intervention', label: 'Intervention' },
  { value: 'protocol', label: 'Protocol' },
  { value: 'other', label: 'Other' },
]

interface EditableCandidate extends ExtractedTreatmentCandidate {
  id: string
  selected: boolean
  ongoing: boolean
}

interface TreatmentReviewDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  candidates: ExtractedTreatmentCandidate[]
  extractionMeta?: { model: string; confidence: number; attempts: number } | null
}

function toEditable(c: ExtractedTreatmentCandidate, index: number): EditableCandidate {
  return {
    ...c,
    id: `c-${index}`,
    selected: true,
    ongoing: !c.end_date,
  }
}

export function TreatmentReviewDialog({
  open,
  onOpenChange,
  candidates,
  extractionMeta,
}: TreatmentReviewDialogProps) {
  const [rows, setRows] = useState<EditableCandidate[]>(() => candidates.map(toEditable))
  const createMutation = useCreateTreatment()

  function updateRow(id: string, patch: Partial<EditableCandidate>) {
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, ...patch } : r)))
  }

  async function handleSave() {
    const selected = rows.filter((r) => r.selected)
    if (selected.length === 0) {
      toast.error('Select at least one treatment to save')
      return
    }

    for (const row of selected) {
      if (!row.name.trim()) {
        toast.error('Every selected treatment needs a name')
        return
      }
      if (!row.start_date) {
        toast.error('Every selected treatment needs a start date')
        return
      }
      if (row.doses_per_day != null && (row.doses_per_day < 1 || row.doses_per_day > 12)) {
        toast.error('Doses per day must be between 1 and 12')
        return
      }
      const endDate = row.ongoing ? null : row.end_date
      if (endDate && endDate < row.start_date) {
        toast.error('End date must be on or after start date')
        return
      }
    }

    try {
      for (const row of selected) {
        await createMutation.mutateAsync({
          name: row.name.trim(),
          type: row.type,
          group_name: row.group_name?.trim() || null,
          start_date: row.start_date,
          end_date: row.ongoing ? null : row.end_date,
          dose: row.dose?.trim() || null,
          doses_per_day: row.doses_per_day,
          notes: row.notes?.trim() || null,
        })
        setRows((prev) =>
          prev.map((r) => (r.id === row.id ? { ...r, selected: false } : r)),
        )
      }
      toast.success(
        selected.length === 1
          ? 'Treatment added'
          : `${selected.length} treatments added`,
      )
      onOpenChange(false)
    } catch (err) {
      handleMutationError(err, 'Failed to save treatments')
    }
  }

  const selectedCount = rows.filter((r) => r.selected).length

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] w-[calc(100vw-2rem)] max-w-lg overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Review extracted treatments</DialogTitle>
          <DialogDescription>
            Edit each medication before saving. Uncheck any you do not want to import.
          </DialogDescription>
        </DialogHeader>

        {extractionMeta && (
          <div className="rounded-lg border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
            Extracted {candidates.length} treatment{candidates.length === 1 ? '' : 's'} &middot;
            confidence {Math.round(extractionMeta.confidence * 100)}% &middot; attempt
            {extractionMeta.attempts > 1 ? `s ${extractionMeta.attempts}` : ' 1'}
            {extractionMeta.confidence < 0.7 && (
              <span className="ml-1.5 font-medium text-amber-600">— marked for review</span>
            )}
          </div>
        )}

        <div className="space-y-4">
          {rows.map((row) => (
            <div
              key={row.id}
              className={cn(
                'space-y-3 rounded-lg border border-border p-3',
                !row.selected && 'opacity-60',
              )}
            >
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={row.selected}
                  onChange={(e) => updateRow(row.id, { selected: e.target.checked })}
                  className="size-4 rounded border-border"
                />
                <span className="text-sm font-medium">Include this treatment</span>
              </label>

              <div className="space-y-1.5">
                <Label>Name</Label>
                <Input
                  value={row.name}
                  onChange={(e) => updateRow(row.id, { name: e.target.value })}
                />
              </div>

              <div className="space-y-1.5">
                <Label>Type</Label>
                <div className="grid grid-cols-3 gap-1.5">
                  {TREATMENT_TYPES.map((t) => (
                    <button
                      key={t.value}
                      type="button"
                      onClick={() => updateRow(row.id, { type: t.value })}
                      className={cn(
                        'rounded-lg border px-2 py-1.5 text-xs font-medium transition-colors',
                        row.type === t.value
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-border text-muted-foreground hover:bg-muted',
                      )}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label>Start date</Label>
                  <Input
                    type="date"
                    value={row.start_date}
                    onChange={(e) => updateRow(row.id, { start_date: e.target.value })}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>End date</Label>
                  <Input
                    type="date"
                    value={row.end_date ?? ''}
                    disabled={row.ongoing}
                    onChange={(e) =>
                      updateRow(row.id, { end_date: e.target.value || null, ongoing: false })
                    }
                  />
                </div>
              </div>

              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={row.ongoing}
                  onChange={(e) =>
                    updateRow(row.id, {
                      ongoing: e.target.checked,
                      end_date: e.target.checked ? null : row.end_date,
                    })
                  }
                  className="size-4 rounded border-border"
                />
                <span className="text-sm text-muted-foreground">Ongoing (no end date)</span>
              </label>

              <div className="space-y-1.5">
                <Label>Dose</Label>
                <Input
                  value={row.dose ?? ''}
                  onChange={(e) => updateRow(row.id, { dose: e.target.value || null })}
                />
              </div>

              <div className="space-y-1.5">
                <Label>Doses per day</Label>
                <Input
                  type="number"
                  min={1}
                  max={12}
                  value={row.doses_per_day ?? ''}
                  onChange={(e) => {
                    const v = e.target.value
                    updateRow(row.id, {
                      doses_per_day: v === '' ? null : Number(v),
                    })
                  }}
                  className="max-w-24"
                />
              </div>

              <div className="space-y-1.5">
                <Label>Group</Label>
                <Input
                  value={row.group_name ?? ''}
                  onChange={(e) => updateRow(row.id, { group_name: e.target.value || null })}
                />
              </div>

              <div className="space-y-1.5">
                <Label>Notes</Label>
                <Textarea
                  value={row.notes ?? ''}
                  onChange={(e) => updateRow(row.id, { notes: e.target.value || null })}
                  rows={2}
                />
              </div>
            </div>
          ))}
        </div>

        <DialogFooter>
          <Button onClick={handleSave} disabled={createMutation.isPending || selectedCount === 0}>
            {createMutation.isPending
              ? 'Saving...'
              : `Save ${selectedCount} treatment${selectedCount === 1 ? '' : 's'}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

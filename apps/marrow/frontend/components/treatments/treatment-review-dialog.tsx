'use client'

import { useEffect } from 'react'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@f0rge/ui'
import { Button, cn } from '@f0rge/ui'
import { Checkbox, NumberInput, Textarea, TextInput, useForm } from '@f0rge/ui/forms'
import { useCreateTreatment } from '@/lib/api/hooks'
import { handleMutationError } from '@f0rge/ui/api'
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
  const createMutation = useCreateTreatment()

  const form = useForm({
    initialValues: {
      rows: candidates.map(toEditable),
    },
  })

  useEffect(() => {
    if (!open) return
    form.setValues({ rows: candidates.map(toEditable) })
  }, [open, candidates, form])

  const handleSave = form.onSubmit(async ({ rows }) => {
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

    const savedIds: string[] = []
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
        savedIds.push(row.id)
      }
      toast.success(
        selected.length === 1
          ? 'Treatment added'
          : `${selected.length} treatments added`,
      )
      onOpenChange(false)
    } catch (err) {
      if (savedIds.length > 0) {
        form.setValues({
          rows: rows.filter((r) => !savedIds.includes(r.id)),
        })
        toast.warning(
          savedIds.length === 1
            ? '1 treatment saved before the error'
            : `${savedIds.length} treatments saved before the error`,
        )
      }
      handleMutationError(err, 'Failed to save treatments')
    }
  })

  const rows = form.values.rows
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

        <form onSubmit={handleSave} className="space-y-4">
          {rows.map((row, index) => (
            <div
              key={row.id}
              className={cn(
                'space-y-3 rounded-lg border border-border p-3',
                !row.selected && 'opacity-60',
              )}
            >
              <Checkbox
                label="Include this treatment"
                checked={row.selected}
                onChange={(event) =>
                  form.setFieldValue(`rows.${index}.selected`, event.currentTarget.checked)
                }
              />

              <TextInput
                label="Name"
                {...form.getInputProps(`rows.${index}.name`)}
              />

              <div className="space-y-1.5">
                <p className="text-sm font-medium leading-none">Type</p>
                <div className="grid grid-cols-3 gap-1.5">
                  {TREATMENT_TYPES.map((t) => (
                    <button
                      key={t.value}
                      type="button"
                      onClick={() => form.setFieldValue(`rows.${index}.type`, t.value)}
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
                <TextInput
                  label="Start date"
                  type="date"
                  {...form.getInputProps(`rows.${index}.start_date`)}
                />
                <TextInput
                  label="End date"
                  type="date"
                  disabled={row.ongoing}
                  value={row.end_date ?? ''}
                  onChange={(event) => {
                    form.setFieldValue(`rows.${index}.end_date`, event.currentTarget.value || null)
                    form.setFieldValue(`rows.${index}.ongoing`, false)
                  }}
                />
              </div>

              <Checkbox
                label="Ongoing (no end date)"
                checked={row.ongoing}
                onChange={(event) => {
                  const checked = event.currentTarget.checked
                  form.setFieldValue(`rows.${index}.ongoing`, checked)
                  if (checked) form.setFieldValue(`rows.${index}.end_date`, null)
                }}
              />

              <TextInput
                label="Dose"
                value={row.dose ?? ''}
                onChange={(event) =>
                  form.setFieldValue(`rows.${index}.dose`, event.currentTarget.value || null)
                }
              />

              <NumberInput
                label="Doses per day"
                min={1}
                max={12}
                className="max-w-24"
                value={row.doses_per_day ?? ''}
                onChange={(value) =>
                  form.setFieldValue(`rows.${index}.doses_per_day`, value === '' ? null : Number(value))
                }
              />

              <TextInput
                label="Group"
                value={row.group_name ?? ''}
                onChange={(event) =>
                  form.setFieldValue(`rows.${index}.group_name`, event.currentTarget.value || null)
                }
              />

              <Textarea
                label="Notes"
                minRows={2}
                value={row.notes ?? ''}
                onChange={(event) =>
                  form.setFieldValue(`rows.${index}.notes`, event.currentTarget.value || null)
                }
              />
            </div>
          ))}

          <DialogFooter>
            <Button type="submit" disabled={createMutation.isPending || selectedCount === 0}>
              {createMutation.isPending
                ? 'Saving...'
                : `Save ${selectedCount} treatment${selectedCount === 1 ? '' : 's'}`}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

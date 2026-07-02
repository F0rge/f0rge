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
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useCreateTreatment, useUpdateTreatment, useDeleteTreatment } from '@/lib/api/hooks'
import type { Treatment, TreatmentType } from '@/lib/api/types'
import { cn, formatLocalDate } from '@/lib/utils'

interface TreatmentFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  treatment?: Treatment | null
}

const TREATMENT_TYPES: { value: TreatmentType; label: string }[] = [
  { value: 'antibiotic', label: 'Antibiotic' },
  { value: 'antimicrobial', label: 'Antimicrobial' },
  { value: 'prescription', label: 'Prescription' },
  { value: 'intervention', label: 'Intervention' },
  { value: 'protocol', label: 'Protocol' },
  { value: 'other', label: 'Other' },
]

export function TreatmentFormDialog({ open, onOpenChange, treatment }: TreatmentFormDialogProps) {
  const isEdit = !!treatment
  const [name, setName] = useState(treatment?.name ?? '')
  const [type, setType] = useState<TreatmentType>(treatment?.type ?? 'other')
  const [startDate, setStartDate] = useState(treatment?.start_date ?? formatLocalDate(new Date()))
  const [endDate, setEndDate] = useState(treatment?.end_date ?? '')
  const [ongoing, setOngoing] = useState(!treatment?.end_date)
  const [dose, setDose] = useState(treatment?.dose ?? '')
  const [notes, setNotes] = useState(treatment?.notes ?? '')
  const [confirmDelete, setConfirmDelete] = useState(false)

  const createMutation = useCreateTreatment()
  const updateMutation = useUpdateTreatment()
  const deleteMutation = useDeleteTreatment()

  async function handleSubmit() {
    if (!name.trim()) {
      toast.error('Name is required')
      return
    }
    if (!startDate) {
      toast.error('Start date is required')
      return
    }
    const finalEnd = ongoing ? null : endDate || null
    if (finalEnd && finalEnd < startDate) {
      toast.error('End date must be on or after start date')
      return
    }

    const payload = {
      name: name.trim(),
      type,
      start_date: startDate,
      end_date: finalEnd,
      dose: dose.trim() || null,
      notes: notes.trim() || null,
    }

    try {
      if (isEdit) {
        await updateMutation.mutateAsync({ id: treatment.id, data: payload })
        toast.success('Treatment updated')
      } else {
        await createMutation.mutateAsync(payload)
        toast.success('Treatment added')
      }
      onOpenChange(false)
    } catch {
      toast.error(isEdit ? 'Failed to update treatment' : 'Failed to add treatment')
    }
  }

  async function handleDelete() {
    if (!treatment) return
    if (!confirmDelete) {
      setConfirmDelete(true)
      return
    }
    try {
      await deleteMutation.mutateAsync(treatment.id)
      toast.success('Treatment deleted')
      onOpenChange(false)
    } catch {
      toast.error('Failed to delete treatment')
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending || deleteMutation.isPending

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Edit Treatment' : 'Add Treatment'}</DialogTitle>
          <DialogDescription>
            Track a treatment course. Leave the end date empty while ongoing.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="tx-name">Name</Label>
            <Input
              id="tx-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Rifaximin"
            />
          </div>

          <div className="space-y-1.5">
            <Label>Type</Label>
            <div className="grid grid-cols-3 gap-1.5">
              {TREATMENT_TYPES.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => setType(t.value)}
                  className={cn(
                    'rounded-lg border px-2 py-2 text-xs font-medium transition-colors',
                    type === t.value
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
              <Label htmlFor="tx-start">Start date</Label>
              <Input
                id="tx-start"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="tx-end">End date</Label>
              <Input
                id="tx-end"
                type="date"
                value={endDate}
                onChange={(e) => { setEndDate(e.target.value); setOngoing(false) }}
              />
            </div>
          </div>

          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={ongoing}
              onChange={(e) => {
                setOngoing(e.target.checked)
                if (e.target.checked) setEndDate('')
              }}
              className="size-4 rounded border-border"
            />
            <span className="text-sm text-muted-foreground">Ongoing (no end date)</span>
          </label>

          <div className="space-y-1.5">
            <Label htmlFor="tx-dose">Dose</Label>
            <Input
              id="tx-dose"
              value={dose}
              onChange={(e) => setDose(e.target.value)}
              placeholder="e.g. 550mg 3x daily"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="tx-notes">Notes</Label>
            <Textarea
              id="tx-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional notes..."
              rows={3}
            />
          </div>
        </div>

        <DialogFooter>
          {isEdit && (
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={isPending}
              className="sm:mr-auto"
            >
              {confirmDelete ? 'Confirm delete' : 'Delete'}
            </Button>
          )}
          <Button onClick={handleSubmit} disabled={isPending}>
            {isPending ? 'Saving...' : isEdit ? 'Save' : 'Add treatment'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

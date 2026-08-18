'use client'

import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@f0rge/ui'
import { Button, cn, formatLocalDate } from '@f0rge/ui'
import { Checkbox, NumberInput, Textarea, TextInput, useForm } from '@f0rge/ui/forms'
import { useTreatments, useCreateTreatment, useUpdateTreatment, useDeleteTreatment } from '@/lib/api/hooks'
import { handleMutationError } from '@f0rge/ui/api'
import type { Treatment, TreatmentType } from '@/lib/api/types'

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

function initialValues(treatment?: Treatment | null) {
  return {
    name: treatment?.name ?? '',
    type: (treatment?.type ?? 'other') as TreatmentType,
    group: treatment?.group_name ?? '',
    startDate: treatment?.start_date ?? formatLocalDate(new Date()),
    endDate: treatment?.end_date ?? '',
    ongoing: !treatment?.end_date,
    dose: treatment?.dose ?? '',
    dosesPerDay: treatment?.doses_per_day != null ? String(treatment.doses_per_day) : '',
    notes: treatment?.notes ?? '',
  }
}

export function TreatmentFormDialog({ open, onOpenChange, treatment }: TreatmentFormDialogProps) {
  const isEdit = !!treatment
  const [confirmDelete, setConfirmDelete] = useState(false)

  const form = useForm({
    mode: 'uncontrolled',
    initialValues: initialValues(treatment),
    validate: {
      name: (value) => (value.trim() ? null : 'Name is required'),
      startDate: (value) => (value ? null : 'Start date is required'),
      dosesPerDay: (value) => {
        if (!value.trim()) return null
        const parsed = Number(value)
        if (!Number.isInteger(parsed) || parsed < 1 || parsed > 12) {
          return 'Doses per day must be a whole number between 1 and 12'
        }
        return null
      },
    },
  })

  useEffect(() => {
    if (!open) return
    form.setValues(initialValues(treatment))
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset delete confirmation when dialog reopens
    setConfirmDelete(false)
    // form object identity changes after setValues in Mantine 8
  }, [open, treatment])

  const { data: existingTreatments } = useTreatments()
  const groupOptions = Array.from(
    new Map(
      (existingTreatments ?? [])
        .map((t) => t.group_name)
        .filter((g): g is string => !!g)
        .map((g) => [g.toLowerCase(), g]),
    ).values(),
  ).sort((a, b) => a.localeCompare(b))

  const createMutation = useCreateTreatment()
  const updateMutation = useUpdateTreatment()
  const deleteMutation = useDeleteTreatment()

  const handleSubmit = form.onSubmit(async (values) => {
    const finalEnd = values.ongoing ? null : values.endDate || null
    if (finalEnd && finalEnd < values.startDate) {
      toast.error('End date must be on or after start date')
      return
    }

    const payload = {
      name: values.name.trim(),
      type: values.type,
      group_name: values.group.trim() || null,
      start_date: values.startDate,
      end_date: finalEnd,
      dose: values.dose.trim() || null,
      doses_per_day: values.dosesPerDay.trim() ? Number(values.dosesPerDay) : null,
      notes: values.notes.trim() || null,
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
    } catch (err) {
      handleMutationError(err, isEdit ? 'Failed to update treatment' : 'Failed to add treatment')
    }
  })

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
    } catch (err) {
      handleMutationError(err, 'Failed to delete treatment')
    }
  }

  const isPending = createMutation.isPending || updateMutation.isPending || deleteMutation.isPending
  const type = form.getValues().type
  const ongoing = form.getValues().ongoing

  const endDateProps = form.getInputProps('endDate')
  const { onChange: onEndDateChange, ...endDateFieldProps } = endDateProps

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Edit Treatment' : 'Add Treatment'}</DialogTitle>
          <DialogDescription>
            Track a treatment course. Leave the end date empty while ongoing.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <TextInput
            key={form.key('name')}
            label="Name"
            placeholder="e.g. Rifaximin"
            {...form.getInputProps('name')}
          />

          <div className="space-y-1.5">
            <p className="text-sm font-medium leading-none">Type</p>
            <div className="grid grid-cols-3 gap-1.5">
              {TREATMENT_TYPES.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => form.setFieldValue('type', t.value)}
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

          <TextInput
            key={form.key('group')}
            label="Group"
            placeholder="e.g. SIBO Treatment"
            maxLength={100}
            list="tx-group-options"
            {...form.getInputProps('group')}
          />
          <datalist id="tx-group-options">
            {groupOptions.map((g) => (
              <option key={g} value={g} />
            ))}
          </datalist>

          <div className="grid grid-cols-2 gap-3">
            <TextInput
              key={form.key('startDate')}
              label="Start date"
              type="date"
              {...form.getInputProps('startDate')}
            />
            <TextInput
              key={form.key('endDate')}
              label="End date"
              type="date"
              disabled={ongoing}
              {...endDateFieldProps}
              onChange={(event) => {
                onEndDateChange?.(event)
                form.setFieldValue('ongoing', false)
              }}
            />
          </div>

          <Checkbox
            label="Ongoing (no end date)"
            checked={ongoing}
            onChange={(event) => {
              const checked = event.currentTarget.checked
              form.setFieldValue('ongoing', checked)
              if (checked) form.setFieldValue('endDate', '')
            }}
          />

          <TextInput
            key={form.key('dose')}
            label="Dose"
            placeholder="e.g. 550mg 3x daily"
            {...form.getInputProps('dose')}
          />

          <NumberInput
            key={form.key('dosesPerDay')}
            label="Doses per day"
            placeholder="e.g. 3"
            min={1}
            max={12}
            className="max-w-24"
            description="How many times a day you take this. Leave blank for non-dose treatments (e.g. a diet)."
            {...form.getInputProps('dosesPerDay')}
          />

          <Textarea
            key={form.key('notes')}
            label="Notes"
            placeholder="Optional notes..."
            minRows={3}
            {...form.getInputProps('notes')}
          />

          <DialogFooter>
            {isEdit && (
              <Button
                type="button"
                variant="destructive"
                onClick={handleDelete}
                disabled={isPending}
                className="sm:mr-auto"
              >
                {confirmDelete ? 'Confirm delete' : 'Delete'}
              </Button>
            )}
            <Button type="submit" disabled={isPending}>
              {isPending ? 'Saving...' : isEdit ? 'Save' : 'Add treatment'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

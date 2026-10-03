'use client'

import { toast } from 'sonner'
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  Button,
} from '@f0rge/ui'
import { Select, Textarea, useForm } from '@f0rge/ui/forms'
import { useUpdateTreatment } from '@/lib/api/hooks'
import { handleMutationError } from '@f0rge/ui/api'
import type { Treatment } from '@/lib/api/types'
import { formatLocalDate } from '@f0rge/ui'
import { END_REASON_OPTIONS } from './end-reason'

interface DiscontinueDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  treatment: Treatment
}

export function DiscontinueDialog({ open, onOpenChange, treatment }: DiscontinueDialogProps) {
  const isCorrection = !!treatment.end_date
  const updateMutation = useUpdateTreatment()

  const form = useForm({
    mode: 'uncontrolled',
    initialValues: {
      reason: treatment.end_reason ?? '',
      note: treatment.end_note ?? '',
    },
    validate: {
      reason: (value) => (value ? null : 'Select a reason'),
    },
  })

  const handleConfirm = form.onSubmit(async (values) => {
    try {
      await updateMutation.mutateAsync({
        id: treatment.id,
        data: {
          end_date: treatment.end_date ?? formatLocalDate(new Date()),
          end_reason: values.reason,
          end_note: values.note.trim() || null,
        },
      })
      toast.success(isCorrection ? 'Reason updated' : 'Treatment discontinued')
      onOpenChange(false)
    } catch (err) {
      handleMutationError(err, 'Failed to discontinue treatment')
    }
  })

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="sm:max-w-md">
        <AlertDialogHeader className="text-left sm:text-left">
          <AlertDialogTitle>{isCorrection ? 'Update reason' : 'Discontinue treatment'}</AlertDialogTitle>
          <AlertDialogDescription>
            {isCorrection
              ? `Update why ${treatment.name} was stopped.`
              : `Record why ${treatment.name} is being stopped.`}
          </AlertDialogDescription>
        </AlertDialogHeader>

        <form onSubmit={handleConfirm} className="space-y-4">
          <Select
            key={form.key('reason')}
            label="Reason"
            placeholder="Select a reason"
            data={END_REASON_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
            {...form.getInputProps('reason')}
          />

          <Textarea
            key={form.key('note')}
            label="Explanation (optional)"
            placeholder="Optional details..."
            maxLength={1000}
            minRows={3}
            {...form.getInputProps('note')}
          />

          <AlertDialogFooter className="sm:justify-end">
            <AlertDialogCancel type="button">Cancel</AlertDialogCancel>
            <Button type="submit" disabled={updateMutation.isPending}>
              {updateMutation.isPending ? 'Saving...' : 'Discontinue'}
            </Button>
          </AlertDialogFooter>
        </form>
      </AlertDialogContent>
    </AlertDialog>
  )
}

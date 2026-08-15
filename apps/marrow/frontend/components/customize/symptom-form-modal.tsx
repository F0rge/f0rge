'use client'

/**
 * SymptomFormModal — create or edit a custom symptom.
 */

import { useEffect } from 'react'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@f0rge/ui'
import { Button } from '@f0rge/ui'
import { TextInput, useForm } from '@f0rge/ui/forms'
import { useAddSymptomCatalogItem, useUpdateSymptomCatalogItem } from '@/lib/api/hooks'
import { ApiError, handleMutationError } from '@f0rge/ui/api'
import type { SymptomCatalogItem } from '@/lib/api/types'

function normalizeKey(label: string): string {
  return label
    .trim()
    .toLowerCase()
    .replace(/[-\s]+/g, '_')
    .replace(/[^a-z0-9_]/g, '')
}

interface SymptomFormModalProps {
  open: boolean
  onClose: () => void
  symptom?: SymptomCatalogItem
}

export function SymptomFormModal({ open, onClose, symptom }: SymptomFormModalProps) {
  const isEdit = symptom !== undefined
  const addSymptom = useAddSymptomCatalogItem()
  const updateSymptom = useUpdateSymptomCatalogItem()
  const isPending = addSymptom.isPending || updateSymptom.isPending

  const form = useForm({
    mode: 'uncontrolled',
    initialValues: { label: symptom?.label ?? '' },
    validate: {
      label: (value) => (value.trim() ? null : 'Label is required'),
    },
  })

  useEffect(() => {
    if (!open) return
    form.setValues({ label: symptom?.label ?? '' })
  }, [open, symptom, form])

  const previewKey = isEdit ? symptom.key : normalizeKey(form.getValues().label)

  function handleClose() {
    onClose()
  }

  const handleSubmit = form.onSubmit(async (values) => {
    try {
      if (isEdit) {
        await updateSymptom.mutateAsync({ key: symptom.key, data: { label: values.label.trim() } })
        toast.success('Symptom updated')
      } else {
        const key = normalizeKey(values.label)
        if (!key) {
          toast.error('Label must contain at least one letter or number')
          return
        }
        await addSymptom.mutateAsync({ key, label: values.label.trim() })
      }
      handleClose()
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        toast.error('A symptom with this key already exists')
      } else {
        handleMutationError(err, 'Failed to save symptom. Please try again.')
      }
    }
  })

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) handleClose() }}>
      <DialogContent className="max-w-sm" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Edit symptom' : 'Add symptom'}</DialogTitle>
          <DialogDescription>
            {isEdit ? 'Update the symptom label.' : 'Name a custom symptom to track daily.'}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <TextInput
              key={form.key('label')}
              label="Label"
              placeholder="e.g. Brain fog"
              autoFocus
              required
              {...form.getInputProps('label')}
            />
            <p className="mt-1 text-[11px] text-muted-foreground">
              Key: <span className="font-mono">{previewKey || '—'}</span>
            </p>
          </div>

          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="ghost" size="sm" onClick={handleClose}>
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={isPending}>
              {isPending
                ? isEdit ? 'Saving…' : 'Adding…'
                : isEdit ? 'Save changes' : 'Add symptom'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

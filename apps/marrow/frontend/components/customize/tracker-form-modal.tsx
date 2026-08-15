'use client'

/**
 * TrackerFormModal — create or edit a custom tracker.
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
import { useCreateTracker, useUpdateTracker } from '@/lib/api/hooks'
import { ApiError, handleMutationError } from '@f0rge/ui/api'
import type { Tracker, TrackerKind } from '@/lib/api/types'
import { IconPicker } from '@/components/checkin/cards/components/IconPicker'

interface TrackerFormModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  tracker?: Tracker
  trackerCount?: number
}

export function TrackerFormModal({
  open,
  onOpenChange,
  tracker,
  trackerCount = 0,
}: TrackerFormModalProps) {
  const isEdit = tracker !== undefined
  const createTracker = useCreateTracker()
  const updateTracker = useUpdateTracker()
  const isPending = createTracker.isPending || updateTracker.isPending

  const form = useForm({
    mode: 'uncontrolled',
    initialValues: {
      name: tracker?.name ?? '',
      kind: (tracker?.kind ?? 'counter') as TrackerKind,
      icon: tracker?.icon ?? '',
      unit: tracker?.unit ?? '',
    },
    validate: {
      name: (value) => (value.trim() ? null : 'Name is required'),
    },
  })

  useEffect(() => {
    if (!open) return
    form.setValues({
      name: tracker?.name ?? '',
      kind: tracker?.kind ?? 'counter',
      icon: tracker?.icon ?? '',
      unit: tracker?.unit ?? '',
    })
  }, [open, tracker, form])

  function handleClose() {
    onOpenChange(false)
  }

  const handleSubmit = form.onSubmit(async (values) => {
    const icon = values.icon || null
    try {
      if (isEdit) {
        await updateTracker.mutateAsync({
          id: tracker.id,
          data: {
            name: values.name.trim(),
            icon,
            unit: tracker.kind === 'counter' && values.unit.trim() ? values.unit.trim() : null,
          },
        })
        toast.success('Tracker updated')
      } else {
        await createTracker.mutateAsync({
          name: values.name.trim(),
          kind: values.kind,
          icon,
          unit: values.kind === 'counter' && values.unit.trim() ? values.unit.trim() : null,
          position: trackerCount,
        })
      }
      handleClose()
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        toast.error('A tracker with this name already exists')
      } else {
        handleMutationError(err, 'Failed to save tracker. Please try again.')
      }
    }
  })

  const effectiveKind = isEdit ? tracker.kind : form.getValues().kind

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Edit tracker' : 'Add tracker'}</DialogTitle>
          <DialogDescription>
            {isEdit ? 'Update the tracker name, icon, or unit.' : 'Set up a new custom tracker.'}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <TextInput
            key={form.key('name')}
            label="Name"
            placeholder="e.g. Steps"
            autoFocus
            required
            {...form.getInputProps('name')}
          />

          <div className="space-y-1.5">
            <p className="text-xs text-muted-foreground">Type</p>
            {isEdit ? (
              <p className="text-sm text-muted-foreground capitalize">{tracker.kind}</p>
            ) : (
              <div className="grid grid-cols-2 gap-1 rounded-md bg-muted p-1">
                {(['counter', 'binary'] as TrackerKind[]).map((k) => (
                  <button
                    key={k}
                    type="button"
                    onClick={() => form.setFieldValue('kind', k)}
                    className={`rounded py-1.5 text-xs font-medium transition-all ${
                      form.getValues().kind === k
                        ? 'bg-card text-foreground shadow-sm'
                        : 'text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    {k === 'counter' ? 'Counter' : 'Binary'}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-1.5">
            <p className="text-xs text-muted-foreground">Icon</p>
            <IconPicker
              value={form.getValues().icon || null}
              onChange={(icon) => form.setFieldValue('icon', icon ?? '')}
            />
          </div>

          {effectiveKind === 'counter' && (
            <TextInput
              key={form.key('unit')}
              label="Unit (optional)"
              placeholder="e.g. glasses, mg, minutes"
              {...form.getInputProps('unit')}
            />
          )}

          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="ghost" size="sm" onClick={handleClose}>
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={isPending}>
              {isPending
                ? isEdit ? 'Saving…' : 'Adding…'
                : isEdit ? 'Save changes' : 'Add tracker'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

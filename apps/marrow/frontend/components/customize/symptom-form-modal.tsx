'use client'

/**
 * SymptomFormModal — create or edit a custom symptom.
 *
 * Create mode: symptom prop is undefined → calls useAddSymptomCatalogItem on submit.
 * Edit mode:   symptom prop is defined  → calls useUpdateSymptomCatalogItem on submit.
 *
 * The key field is auto-generated from the label via normalizeKey and shown
 * as a preview below the label input. The key is immutable after creation.
 */

import { useState } from 'react'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@f0rge/ui'
import { Button } from '@f0rge/ui'
import { Input } from '@f0rge/ui'
import { Label } from '@f0rge/ui'
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
  /** Provide to enter edit mode; omit for create mode. */
  symptom?: SymptomCatalogItem
}

export function SymptomFormModal({ open, onClose, symptom }: SymptomFormModalProps) {
  const isEdit = symptom !== undefined

  const [label, setLabel] = useState(symptom?.label ?? '')

  const addSymptom = useAddSymptomCatalogItem()
  const updateSymptom = useUpdateSymptomCatalogItem()
  const isPending = addSymptom.isPending || updateSymptom.isPending

  const previewKey = isEdit ? symptom.key : normalizeKey(label)

  function handleClose() {
    onClose()
    setLabel(symptom?.label ?? '')
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!label.trim()) return

    try {
      if (isEdit) {
        await updateSymptom.mutateAsync({ key: symptom.key, data: { label: label.trim() } })
        toast.success('Symptom updated')
      } else {
        const key = normalizeKey(label)
        if (!key) {
          toast.error('Label must contain at least one letter or number')
          return
        }
        await addSymptom.mutateAsync({ key, label: label.trim() })
      }
      handleClose()
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        toast.error('A symptom with this key already exists')
      } else {
        handleMutationError(err, 'Failed to save symptom. Please try again.')
      }
    }
  }

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
          {/* Label */}
          <div className="space-y-1.5">
            <Label htmlFor="symptom-label" className="text-xs text-muted-foreground">
              Label
            </Label>
            <Input
              id="symptom-label"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g. Brain fog"
              autoFocus
              required
            />
            {/* Key preview */}
            <p className="text-[11px] text-muted-foreground">
              Key: <span className="font-mono">{previewKey || '—'}</span>
            </p>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="ghost" size="sm" onClick={handleClose}>
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={!label.trim() || isPending}>
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

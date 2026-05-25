'use client'

/**
 * TrackerFormModal — create or edit a custom tracker.
 *
 * Create mode: tracker prop is undefined → calls useCreateTracker on submit.
 * Edit mode:   tracker prop is defined  → calls useUpdateTracker on submit.
 *              kind is immutable at the backend, shown as read-only text in edit mode.
 */

import { useState } from 'react'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useCreateTracker, useUpdateTracker } from '@/lib/api/hooks'
import { ApiError } from '@/lib/api/client'
import type { Tracker, TrackerKind } from '@/lib/api/types'
import { IconPicker } from '@/components/checkin/cards/components/IconPicker'

interface TrackerFormModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Provide to enter edit mode; omit for create mode. */
  tracker?: Tracker
  /** Total active tracker count — used to set position on create. */
  trackerCount?: number
}

export function TrackerFormModal({
  open,
  onOpenChange,
  tracker,
  trackerCount = 0,
}: TrackerFormModalProps) {
  const isEdit = tracker !== undefined

  const [name, setName] = useState(tracker?.name ?? '')
  const [kind, setKind] = useState<TrackerKind>(tracker?.kind ?? 'counter')
  const [icon, setIcon] = useState<string | null>(tracker?.icon ?? null)
  const [unit, setUnit] = useState(tracker?.unit ?? '')

  const createTracker = useCreateTracker()
  const updateTracker = useUpdateTracker()
  const isPending = createTracker.isPending || updateTracker.isPending

  function handleClose() {
    onOpenChange(false)
    // Reset to tracker values (or defaults) on close
    setName(tracker?.name ?? '')
    setKind(tracker?.kind ?? 'counter')
    setIcon(tracker?.icon ?? null)
    setUnit(tracker?.unit ?? '')
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) return

    try {
      if (isEdit) {
        await updateTracker.mutateAsync({
          id: tracker.id,
          data: {
            name: name.trim(),
            icon: icon ?? null,
            unit: tracker.kind === 'counter' && unit.trim() ? unit.trim() : null,
          },
        })
        toast.success('Tracker updated')
      } else {
        await createTracker.mutateAsync({
          name: name.trim(),
          kind,
          icon: icon ?? null,
          unit: kind === 'counter' && unit.trim() ? unit.trim() : null,
          position: trackerCount,
        })
      }
      handleClose()
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        toast.error('A tracker with this name already exists')
      } else {
        console.error(err)
        toast.error('Failed to save tracker. Please try again.')
      }
    }
  }

  const effectiveKind = isEdit ? tracker.kind : kind

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-sm" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Edit tracker' : 'Add tracker'}</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Name */}
          <div className="space-y-1.5">
            <Label htmlFor="tracker-name" className="text-xs text-muted-foreground">
              Name
            </Label>
            <Input
              id="tracker-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Steps"
              autoFocus
              required
            />
          </div>

          {/* Type — segmented control in create mode, read-only text in edit mode */}
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Type</Label>
            {isEdit ? (
              <p className="text-sm text-muted-foreground capitalize">{tracker.kind}</p>
            ) : (
              <div className="grid grid-cols-2 gap-1 p-1 bg-muted rounded-md">
                {(['counter', 'binary'] as TrackerKind[]).map((k) => (
                  <button
                    key={k}
                    type="button"
                    onClick={() => setKind(k)}
                    className={`py-1.5 rounded text-xs font-medium transition-all ${
                      kind === k
                        ? 'bg-card shadow-sm text-foreground'
                        : 'text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    {k === 'counter' ? 'Counter' : 'Binary'}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Icon picker */}
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Icon</Label>
            <IconPicker value={icon} onChange={setIcon} />
          </div>

          {/* Unit — only for counter */}
          {effectiveKind === 'counter' && (
            <div className="space-y-1.5">
              <Label htmlFor="tracker-unit" className="text-xs text-muted-foreground">
                Unit (optional)
              </Label>
              <Input
                id="tracker-unit"
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                placeholder="e.g. glasses, mg, minutes"
              />
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-2 pt-1">
            <Button type="button" variant="ghost" size="sm" onClick={handleClose}>
              Cancel
            </Button>
            <Button type="submit" size="sm" disabled={!name.trim() || isPending}>
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

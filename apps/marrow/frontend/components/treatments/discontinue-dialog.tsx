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
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useUpdateTreatment } from '@/lib/api/hooks'
import { handleMutationError } from '@/lib/api/client'
import type { Treatment } from '@/lib/api/types'
import { formatLocalDate } from '@/lib/utils'
import { END_REASON_OPTIONS } from './end-reason'

interface DiscontinueDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  treatment: Treatment
}

export function DiscontinueDialog({ open, onOpenChange, treatment }: DiscontinueDialogProps) {
  const isCorrection = !!treatment.end_date
  const [reason, setReason] = useState(treatment.end_reason ?? '')
  const [note, setNote] = useState(treatment.end_note ?? '')
  const updateMutation = useUpdateTreatment()

  const selectedLabel = END_REASON_OPTIONS.find((o) => o.value === reason)?.label ?? 'Select a reason'

  async function handleConfirm() {
    if (!reason) {
      toast.error('Select a reason')
      return
    }
    try {
      await updateMutation.mutateAsync({
        id: treatment.id,
        data: {
          end_date: treatment.end_date ?? formatLocalDate(new Date()),
          end_reason: reason,
          end_note: note.trim() || null,
        },
      })
      toast.success(isCorrection ? 'Reason updated' : 'Treatment discontinued')
      onOpenChange(false)
    } catch (err) {
      handleMutationError(err, 'Failed to discontinue treatment')
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{isCorrection ? 'Update reason' : 'Discontinue treatment'}</DialogTitle>
          <DialogDescription>
            {isCorrection
              ? `Update why ${treatment.name} was stopped.`
              : `Record why ${treatment.name} is being stopped.`}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="discontinue-reason">Reason</Label>
            <Select
              value={reason}
              onValueChange={(v) => {
                if (v !== null) setReason(v)
              }}
            >
              <SelectTrigger id="discontinue-reason" className="w-full">
                <SelectValue>{selectedLabel}</SelectValue>
              </SelectTrigger>
              <SelectContent>
                {END_REASON_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="discontinue-note">Explanation (optional)</Label>
            <Textarea
              id="discontinue-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Optional details..."
              rows={3}
              maxLength={1000}
            />
          </div>
        </div>

        <DialogFooter>
          <Button onClick={handleConfirm} disabled={updateMutation.isPending}>
            {updateMutation.isPending ? 'Saving...' : 'Discontinue'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

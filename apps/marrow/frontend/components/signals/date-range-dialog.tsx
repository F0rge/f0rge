'use client'

import {
  Button,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  formatDisplayDate,
} from '@f0rge/ui'
import { TextInput } from '@f0rge/ui/forms'
import { CalendarIcon } from 'lucide-react'

interface Props {
  open: boolean
  start: string
  end: string
  draftStart: string
  draftEnd: string
  rangeInvalid: boolean
  onOpenChange: (open: boolean) => void
  onDraftStart: (value: string) => void
  onDraftEnd: (value: string) => void
  onApply: () => void
}

export function SignalsDateRangeDialog({
  open,
  start,
  end,
  draftStart,
  draftEnd,
  rangeInvalid,
  onOpenChange,
  onDraftStart,
  onDraftEnd,
  onApply,
}: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger
        render={
          <Button variant="outline" size="sm" className="gap-1.5 text-xs" />
        }
      >
        <CalendarIcon className="size-3.5" />
        {formatDisplayDate(start)} — {formatDisplayDate(end)}
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Date range</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <TextInput
            id="signals-start"
            label="Start"
            type="date"
            value={draftStart}
            onChange={(e) => onDraftStart(e.currentTarget.value)}
          />
          <TextInput
            id="signals-end"
            label="End"
            type="date"
            value={draftEnd}
            onChange={(e) => onDraftEnd(e.currentTarget.value)}
          />
          {rangeInvalid ? (
            <p className="text-xs text-destructive">Start must be on or before end.</p>
          ) : null}
          <Button className="w-full" size="sm" onClick={onApply} disabled={rangeInvalid}>
            Apply
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

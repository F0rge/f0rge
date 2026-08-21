'use client'

import { useState } from 'react'
import { CalendarIcon } from 'lucide-react'
import {
  Button,
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
  formatDisplayDate,
} from '@f0rge/ui'
import { TextInput } from '@f0rge/ui/forms'
import { useSymptomCatalog } from '@/lib/api/hooks'

const CORE_OUTCOMES = [
  { value: 'overall', label: 'Overall' },
  { value: 'bloating', label: 'Bloating' },
  { value: 'sleep_quality', label: 'Sleep Quality' },
  { value: 'stress', label: 'Stress' },
  { value: 'sick', label: 'Sick' },
]

interface Props {
  start: string
  end: string
  outcome: string
  onStartChange: (v: string) => void
  onEndChange: (v: string) => void
  onOutcomeChange: (v: string) => void
}

export function SignalsHeaderControls({
  start,
  end,
  outcome,
  onStartChange,
  onEndChange,
  onOutcomeChange,
}: Props) {
  const [dateOpen, setDateOpen] = useState(false)
  const [draftStart, setDraftStart] = useState(start)
  const [draftEnd, setDraftEnd] = useState(end)
  const { data: symptomCatalog } = useSymptomCatalog()

  const symptomOutcomes =
    symptomCatalog?.map((s) => ({
      value: `sym_${s.key}`,
      label: s.label,
    })) ?? []

  function handleDateOpenChange(open: boolean) {
    if (open) {
      setDraftStart(start)
      setDraftEnd(end)
    }
    setDateOpen(open)
  }

  const rangeInvalid = draftStart > draftEnd

  function applyDates() {
    if (rangeInvalid) return
    onStartChange(draftStart)
    onEndChange(draftEnd)
    setDateOpen(false)
  }

  const allOutcomes = [...CORE_OUTCOMES, ...symptomOutcomes]
  const selectedLabel =
    allOutcomes.find((o) => o.value === outcome)?.label ?? outcome

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Dialog open={dateOpen} onOpenChange={handleDateOpenChange}>
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
              onChange={(e) => setDraftStart(e.currentTarget.value)}
            />
            <TextInput
              id="signals-end"
              label="End"
              type="date"
              value={draftEnd}
              onChange={(e) => setDraftEnd(e.currentTarget.value)}
            />
            {rangeInvalid ? (
              <p className="text-xs text-destructive">Start must be on or before end.</p>
            ) : null}
            <Button className="w-full" size="sm" onClick={applyDates} disabled={rangeInvalid}>
              Apply
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Select
        value={outcome}
        onValueChange={(v) => {
          if (v !== null) onOutcomeChange(v)
        }}
      >
        <SelectTrigger className="h-8 w-auto text-xs" aria-label="Outcome">
          <SelectValue>{selectedLabel}</SelectValue>
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectLabel>Core</SelectLabel>
            {CORE_OUTCOMES.map((o) => (
              <SelectItem key={o.value} value={o.value}>
                {o.label}
              </SelectItem>
            ))}
          </SelectGroup>
          {symptomOutcomes.length > 0 && (
            <SelectGroup>
              <SelectLabel>Symptoms</SelectLabel>
              {symptomOutcomes.map((o) => (
                <SelectItem key={o.value} value={o.value}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectGroup>
          )}
        </SelectContent>
      </Select>
    </div>
  )
}

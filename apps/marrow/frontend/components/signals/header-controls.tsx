'use client'

import { useState } from 'react'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@f0rge/ui'
import { useSymptomCatalog } from '@/lib/api/hooks'
import { SignalsDateRangeDialog } from './date-range-dialog'

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
      <SignalsDateRangeDialog
        open={dateOpen}
        start={start}
        end={end}
        draftStart={draftStart}
        draftEnd={draftEnd}
        rangeInvalid={rangeInvalid}
        onOpenChange={handleDateOpenChange}
        onDraftStart={setDraftStart}
        onDraftEnd={setDraftEnd}
        onApply={applyDates}
      />

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

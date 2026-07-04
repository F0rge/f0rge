'use client'

import { useState } from 'react'
import { CalendarIcon } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { useSymptomCatalog } from '@/lib/api/hooks'

const CORE_OUTCOMES = [
  { value: 'overall', label: 'Overall' },
  { value: 'bloating', label: 'Bloating' },
  { value: 'joint_pain', label: 'Joint Pain' },
  { value: 'neuro', label: 'Neuro' },
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

export function HeaderControls({
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

  function applyDates() {
    onStartChange(draftStart)
    onEndChange(draftEnd)
    setDateOpen(false)
  }

  const allOutcomes = [...CORE_OUTCOMES, ...symptomOutcomes]
  const selectedLabel =
    allOutcomes.find((o) => o.value === outcome)?.label ?? outcome

  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Date range picker */}
      <Dialog open={dateOpen} onOpenChange={setDateOpen}>
        <DialogTrigger
          render={
            <Button variant="outline" size="sm" className="gap-1.5 text-xs" />
          }
        >
          <CalendarIcon className="size-3.5" />
          {start} — {end}
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Date range</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <Label className="text-xs">Start</Label>
              <input
                type="date"
                value={draftStart}
                onChange={(e) => setDraftStart(e.target.value)}
                className="h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">End</Label>
              <input
                type="date"
                value={draftEnd}
                onChange={(e) => setDraftEnd(e.target.value)}
                className="h-8 w-full min-w-0 rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>
            <Button className="w-full" size="sm" onClick={applyDates}>
              Apply
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Outcome selector */}
      <Select value={outcome} onValueChange={(v) => { if (v !== null) onOutcomeChange(v) }}>
        <SelectTrigger className="h-8 w-auto text-xs">
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

'use client'

/**
 * MedicationsCard — add-driven "as needed" medication log.
 *
 * Unlike SupplementsCard (a daily on/off chip grid), this card logs each
 * medication as an event the user adds: label, optional dose/reason, and the
 * time it was logged. Value flows through CheckinBoard props via the same
 * autosave path as supplements — no separate fetch/mutation for the per-day
 * log (see MedicationQuickAddDialog for the add flow).
 */

import { useState } from 'react'
import { Pill, X } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { TierPill } from '@/components/customize/tier-pill'
import { MedicationQuickAddDialog } from '@/components/checkin/medication-quick-add-dialog'
import { useMedicationCatalog } from '@/lib/api/hooks'
import type { MedicationIntake } from '@/lib/api/types'

interface MedicationsCardProps {
  value: MedicationIntake[]
  onChange: (v: MedicationIntake[]) => void
}

export function MedicationsCard({ value, onChange }: MedicationsCardProps) {
  const [dialogOpen, setDialogOpen] = useState(false)
  const { data: catalog = [] } = useMedicationCatalog(true)

  const labelFor = (key: string) => catalog.find((m) => m.key === key)?.label ?? key

  function handleAdd(intake: MedicationIntake) {
    onChange([...value, intake])
  }

  function handleRemove(index: number) {
    onChange(value.filter((_, i) => i !== index))
  }

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
          <Pill className="size-4" />
          Medications
          <TierPill tier="catalog" />
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {value.length === 0 ? (
          <p className="py-1 text-sm text-muted-foreground">None taken today</p>
        ) : (
          <div className="space-y-2">
            {value.map((intake, index) => (
              <div
                key={`${intake.key}-${index}`}
                className="flex items-center gap-2.5 rounded-lg border border-border bg-background p-2.5"
              >
                <span className="flex size-7 flex-none items-center justify-center rounded-full bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400">
                  <Pill className="size-3.5" />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold">{labelFor(intake.key)}</div>
                  <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                    {intake.dose && <span>{intake.dose}</span>}
                    {intake.dose && (intake.reason || intake.time) && <span aria-hidden>·</span>}
                    {intake.reason && <span>{intake.reason}</span>}
                    {intake.reason && intake.time && <span aria-hidden>·</span>}
                    {intake.time && <span>{intake.time}</span>}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => handleRemove(index)}
                  aria-label={`Remove ${labelFor(intake.key)}`}
                  className="flex-none text-muted-foreground transition-colors hover:text-foreground"
                >
                  <X className="size-4" />
                </button>
              </div>
            ))}
          </div>
        )}

        <button
          type="button"
          onClick={() => setDialogOpen(true)}
          className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-dashed border-border py-2.5 text-sm font-medium text-foreground transition-colors hover:bg-muted"
        >
          + Add medication
        </button>
      </CardContent>

      <MedicationQuickAddDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onAdd={handleAdd}
      />
    </Card>
  )
}

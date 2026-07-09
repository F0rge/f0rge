'use client'

/**
 * MedicationsCard — catalog pill picker + per-intake log list.
 *
 * Tap a catalog pill to open the log dialog (dose/reason/time). No dashed
 * "+ Add" CTA — matches the Customize-Hub daily-card visual contract.
 */

import { useState } from 'react'
import { Loader2, Pill, X } from 'lucide-react'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { TierPill } from '@/components/customize/tier-pill'
import { MedicationQuickAddDialog } from '@/components/checkin/medication-quick-add-dialog'
import { useMedicationCatalog } from '@/lib/api/hooks'
import { cn } from '@/lib/utils'
import type { MedicationIntake } from '@/lib/api/types'

interface MedicationsCardProps {
  value: MedicationIntake[]
  onChange: (v: MedicationIntake[]) => void
}

export function MedicationsCard({ value, onChange }: MedicationsCardProps) {
  const [dialogOpen, setDialogOpen] = useState(false)
  const [presetKey, setPresetKey] = useState<string | null>(null)
  const { data: activeCatalog = [], isLoading } = useMedicationCatalog(false)
  const { data: fullCatalog = [] } = useMedicationCatalog(true)

  const labelFor = (key: string) => fullCatalog.find((m) => m.key === key)?.label ?? key

  function handleAdd(intake: MedicationIntake) {
    onChange([...value, intake])
  }

  function handleRemove(index: number) {
    onChange(value.filter((_, i) => i !== index))
  }

  function openDialogFor(key: string) {
    setPresetKey(key)
    setDialogOpen(true)
  }

  function handleDialogOpenChange(open: boolean) {
    if (!open) setPresetKey(null)
    setDialogOpen(open)
  }

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
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

        {isLoading ? (
          <div className="flex items-center justify-center py-3 text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
          </div>
        ) : activeCatalog.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No medications in your catalog — pick them in Customize → Catalogs.
          </p>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {activeCatalog.map((med) => (
              <button
                key={med.key}
                type="button"
                onClick={() => openDialogFor(med.key)}
                className={cn(
                  'rounded-full border border-border px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-muted',
                )}
              >
                {med.label}
              </button>
            ))}
          </div>
        )}
      </CardContent>

      <MedicationQuickAddDialog
        key={presetKey ?? 'med-dialog'}
        open={dialogOpen}
        onOpenChange={handleDialogOpenChange}
        onAdd={handleAdd}
        initialKey={presetKey}
      />
    </Card>
  )
}

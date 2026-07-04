'use client'

/**
 * MedicationQuickAddDialog — "Log a medication" quick-add sheet.
 *
 * Mirrors the mockup's Option 1 sheet: pick one med from the active catalog
 * as a chip, optional dose + reason, "Log it" appends a MedicationIntake to
 * the day's array. No API call here — the entry rides the existing autosave
 * path via the parent's onAdd callback (same as SupplementsCard/TrackersCard).
 */

import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { cn, nowHHMM } from '@/lib/utils'
import { useMedicationCatalog } from '@/lib/api/hooks'
import type { MedicationIntake } from '@/lib/api/types'

interface MedicationQuickAddDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onAdd: (intake: MedicationIntake) => void
}

export function MedicationQuickAddDialog({ open, onOpenChange, onAdd }: MedicationQuickAddDialogProps) {
  const { data: catalog = [], isLoading } = useMedicationCatalog(false)
  const [selectedKey, setSelectedKey] = useState<string | null>(null)
  const [dose, setDose] = useState('')
  const [reason, setReason] = useState('')

  function reset() {
    setSelectedKey(null)
    setDose('')
    setReason('')
  }

  function handleOpenChange(v: boolean) {
    if (!v) reset()
    onOpenChange(v)
  }

  function handleLogIt() {
    if (!selectedKey) return
    onAdd({
      key: selectedKey,
      dose: dose.trim() || undefined,
      reason: reason.trim() || undefined,
      time: nowHHMM(),
    })
    handleOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-sm" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>Log a medication</DialogTitle>
          <DialogDescription>
            Pick which one you took. Dose and reason are optional but useful for spotting patterns later.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label className="text-xs text-muted-foreground">Which</Label>
            {isLoading ? (
              <div className="flex items-center justify-center py-3 text-muted-foreground">
                <Loader2 className="size-4 animate-spin" />
              </div>
            ) : catalog.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No medications in your catalog yet — add one in Customize → Catalogs.
              </p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {catalog.map((med) => (
                  <button
                    key={med.key}
                    type="button"
                    onClick={() => setSelectedKey(med.key)}
                    className={cn(
                      'rounded-full border px-3 py-1.5 text-sm transition-colors',
                      selectedKey === med.key
                        ? 'border-primary bg-primary text-primary-foreground'
                        : 'border-border text-muted-foreground hover:bg-muted',
                    )}
                  >
                    {med.label}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="med-dose" className="text-xs text-muted-foreground">
              Dose <span className="normal-case font-normal">(optional)</span>
            </Label>
            <Input
              id="med-dose"
              value={dose}
              onChange={(e) => setDose(e.target.value)}
              placeholder="e.g. 400 mg"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="med-reason" className="text-xs text-muted-foreground">
              Reason <span className="normal-case font-normal">(optional)</span>
            </Label>
            <Input
              id="med-reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g. headache"
            />
          </div>

          <Button
            type="button"
            className="w-full justify-center"
            disabled={!selectedKey}
            onClick={handleLogIt}
          >
            Log it
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

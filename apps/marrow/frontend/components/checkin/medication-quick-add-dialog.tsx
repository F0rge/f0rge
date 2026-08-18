'use client'

import { useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@f0rge/ui'
import { Button, cn, nowHHMM } from '@f0rge/ui'
import { TextInput, useForm } from '@f0rge/ui/forms'
import { useMedicationCatalog } from '@/lib/api/hooks'
import type { MedicationIntake } from '@/lib/api/types'

interface MedicationQuickAddDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onAdd: (intake: MedicationIntake) => void
  initialKey?: string | null
}

export function MedicationQuickAddDialog({
  open,
  onOpenChange,
  onAdd,
  initialKey = null,
}: MedicationQuickAddDialogProps) {
  const { data: catalog = [], isLoading } = useMedicationCatalog(false)

  const form = useForm({
    mode: 'uncontrolled',
    initialValues: {
      selectedKey: initialKey ?? '',
      dose: '',
      reason: '',
    },
    validate: {
      selectedKey: (value) => (value ? null : 'Select a medication'),
    },
  })

  useEffect(() => {
    if (!open) return
    form.setValues({
      selectedKey: initialKey ?? '',
      dose: '',
      reason: '',
    })
    // form object identity changes after setValues in Mantine 8
  }, [open, initialKey])

  function handleOpenChange(v: boolean) {
    if (!v) form.reset()
    onOpenChange(v)
  }

  const handleSubmit = form.onSubmit((values) => {
    onAdd({
      key: values.selectedKey,
      dose: values.dose.trim() || undefined,
      reason: values.reason.trim() || undefined,
      time: nowHHMM(),
    })
    handleOpenChange(false)
  })

  const selectedKey = form.getValues().selectedKey

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-sm" showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>Log a medication</DialogTitle>
          <DialogDescription>
            Pick which one you took. Dose and reason are optional but useful for spotting patterns later.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <p className="text-xs text-muted-foreground">Which</p>
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
                    onClick={() => form.setFieldValue('selectedKey', med.key)}
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
            {form.errors.selectedKey && (
              <p className="text-xs text-destructive">{form.errors.selectedKey}</p>
            )}
          </div>

          <TextInput
            key={form.key('dose')}
            label="Dose (optional)"
            placeholder="e.g. 400 mg"
            {...form.getInputProps('dose')}
          />

          <TextInput
            key={form.key('reason')}
            label="Reason (optional)"
            placeholder="e.g. headache"
            {...form.getInputProps('reason')}
          />

          <Button type="submit" className="w-full justify-center" disabled={!selectedKey}>
            Log it
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  )
}

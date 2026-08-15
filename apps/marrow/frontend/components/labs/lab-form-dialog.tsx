'use client'

import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { Plus, Trash2 } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@f0rge/ui'
import { Button, cn, formatLocalDate } from '@f0rge/ui'
import { NumberInput, Textarea, TextInput, useForm } from '@f0rge/ui/forms'
import { useCreateLab, useUpdateLab } from '@/lib/api/hooks'
import { handleMutationError } from '@f0rge/ui/api'
import { MarkerPicker } from './marker-picker'
import type { Lab, LabType, LabMarkerCreate, ExtractedLabPayload } from '@/lib/api/types'

interface LabFormDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  lab?: Lab | null
  prefill?: ExtractedLabPayload | null
  extractionMeta?: { model: string; confidence: number; attempts: number } | null
}

const LAB_TYPES: { value: LabType; label: string }[] = [
  { value: 'blood', label: 'Blood' },
  { value: 'breath', label: 'Breath' },
  { value: 'imaging', label: 'Imaging' },
  { value: 'microbiology', label: 'Micro' },
  { value: 'allergy', label: 'Allergy' },
  { value: 'comprehensive', label: 'Comprehensive' },
  { value: 'other', label: 'Other' },
]

interface MarkerRow {
  id: string // local key only
  catalog_id: number | null
  canonical_name: string
  display_name: string
  value: string
  value_text: string
  unit: string
  ref_low: string
  ref_high: string
  ref_text: string
}

function emptyRow(): MarkerRow {
  return {
    id: Math.random().toString(36).slice(2),
    catalog_id: null,
    canonical_name: '',
    display_name: '',
    value: '',
    value_text: '',
    unit: '',
    ref_low: '',
    ref_high: '',
    ref_text: '',
  }
}

function prefillRows(payload: ExtractedLabPayload): MarkerRow[] {
  return payload.markers.map((m) => ({
    id: Math.random().toString(36).slice(2),
    catalog_id: null,
    canonical_name: m.canonical_match ?? m.proposed_canonical ?? '',
    display_name: m.display_name,
    value: m.value !== null && m.value !== undefined ? String(m.value) : '',
    value_text: m.value_text ?? '',
    unit: m.unit ?? '',
    ref_low: m.ref_low !== null && m.ref_low !== undefined ? String(m.ref_low) : '',
    ref_high: m.ref_high !== null && m.ref_high !== undefined ? String(m.ref_high) : '',
    ref_text: m.ref_text ?? '',
  }))
}

function labToRows(lab: Lab): MarkerRow[] {
  return lab.markers.map((m) => ({
    id: String(m.id),
    catalog_id: m.catalog_id,
    canonical_name: m.canonical_name,
    display_name: m.display_name,
    value: m.value !== null && m.value !== undefined ? String(m.value) : '',
    value_text: m.value_text ?? '',
    unit: m.unit ?? '',
    ref_low: m.ref_low !== null && m.ref_low !== undefined ? String(m.ref_low) : '',
    ref_high: m.ref_high !== null && m.ref_high !== undefined ? String(m.ref_high) : '',
    ref_text: m.ref_text ?? '',
  }))
}

export function LabFormDialog({ open, onOpenChange, lab, prefill, extractionMeta }: LabFormDialogProps) {
  const isEdit = !!lab

  const initDate = prefill?.lab.lab_date ?? lab?.lab_date ?? formatLocalDate(new Date())
  const initName = prefill?.lab.name ?? lab?.name ?? ''
  const initType: LabType = prefill?.lab.type ?? lab?.type ?? 'blood'
  const initLocation = prefill?.lab.lab_location ?? lab?.lab_location ?? ''
  const initNotes = prefill?.lab.notes ?? lab?.notes ?? ''
  const initRows = prefill ? prefillRows(prefill) : lab ? labToRows(lab) : [emptyRow()]

  const form = useForm({
    mode: 'uncontrolled',
    initialValues: {
      date: initDate,
      name: initName,
      type: initType,
      location: initLocation,
      notes: initNotes,
    },
    validate: {
      date: (value) => (value ? null : 'Date is required'),
      name: (value) => (value.trim() ? null : 'Name is required'),
    },
  })

  const [rows, setRows] = useState<MarkerRow[]>(initRows)

  useEffect(() => {
    if (!open) return
    const date = prefill?.lab.lab_date ?? lab?.lab_date ?? formatLocalDate(new Date())
    const name = prefill?.lab.name ?? lab?.name ?? ''
    const labType: LabType = prefill?.lab.type ?? lab?.type ?? 'blood'
    const location = prefill?.lab.lab_location ?? lab?.lab_location ?? ''
    const notes = prefill?.lab.notes ?? lab?.notes ?? ''
    const nextRows = prefill ? prefillRows(prefill) : lab ? labToRows(lab) : [emptyRow()]
    form.setValues({ date, name, type: labType, location, notes })
    // eslint-disable-next-line react-hooks/set-state-in-effect -- sync marker rows when dialog opens with new lab/prefill
    setRows(nextRows)
  }, [open, lab, prefill, form])

  const createLab = useCreateLab()
  const updateLab = useUpdateLab()

  function updateRow(id: string, patch: Partial<MarkerRow>) {
    setRows((prev) => prev.map((r) => (r.id === id ? { ...r, ...patch } : r)))
  }

  function removeRow(id: string) {
    setRows((prev) => prev.filter((r) => r.id !== id))
  }

  function addRow() {
    setRows((prev) => [...prev, emptyRow()])
  }

  function normalizeCanonical(raw: string): string {
    return raw
      .trim()
      .toLowerCase()
      .replace(/[\s-]+/g, '_')
      .replace(/[^a-z0-9_]/g, '')
  }

  function buildMarkers(): LabMarkerCreate[] {
    return rows
      .filter((r) => {
        const hasName = r.display_name.trim() || r.canonical_name.trim()
        const hasData = r.value !== '' || r.value_text.trim() !== ''
        return hasName && hasData
      })
      .map((r) => {
        const display = r.display_name.trim() || r.canonical_name.trim()
        const canonical =
          r.canonical_name.trim() || normalizeCanonical(display)
        return {
          catalog_id: r.catalog_id ?? 0,
          canonical_name: canonical,
          display_name: display,
          value: r.value !== '' ? parseFloat(r.value) : null,
          value_text: r.value_text.trim() || null,
          unit: r.unit.trim() || null,
          ref_low: r.ref_low !== '' ? parseFloat(r.ref_low) : null,
          ref_high: r.ref_high !== '' ? parseFloat(r.ref_high) : null,
          ref_text: r.ref_text.trim() || null,
        }
      })
  }

  const handleSubmit = form.onSubmit(async (values) => {
    const markers = buildMarkers()
    const payload = {
      lab_date: values.date,
      name: values.name.trim(),
      type: values.type,
      lab_location: values.location.trim() || null,
      notes: values.notes.trim() || null,
      markers,
    }

    try {
      if (isEdit) {
        await updateLab.mutateAsync({ id: lab.id, data: payload })
        toast.success('Lab updated')
      } else {
        await createLab.mutateAsync({ ...payload, source_kind: 'text' })
        toast.success('Lab added')
      }
      onOpenChange(false)
    } catch (err) {
      handleMutationError(err, isEdit ? 'Failed to update lab' : 'Failed to add lab')
    }
  })

  const isPending = createLab.isPending || updateLab.isPending
  const type = form.getValues().type

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? 'Edit Lab' : prefill ? 'Confirm Extracted Lab' : 'Add Lab'}
          </DialogTitle>
          <DialogDescription>
            {isEdit
              ? 'Update lab details and markers.'
              : prefill
                ? 'Review the extracted markers before saving.'
                : 'Enter lab details and markers manually.'}
          </DialogDescription>
        </DialogHeader>

        {extractionMeta && (
          <div className="rounded-lg border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
            Extracted by {extractionMeta.model} &middot; confidence{' '}
            {Math.round(extractionMeta.confidence * 100)}% &middot; attempt
            {extractionMeta.attempts > 1 ? `s ${extractionMeta.attempts}` : ' 1'}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <TextInput
              key={form.key('date')}
              label="Date"
              type="date"
              {...form.getInputProps('date')}
            />
            <TextInput
              key={form.key('name')}
              label="Name"
              placeholder="e.g. Complete Blood Count"
              {...form.getInputProps('name')}
            />
          </div>

          <div className="space-y-1.5">
            <p className="text-sm font-medium leading-none">Type</p>
            <div className="grid grid-cols-4 gap-1.5">
              {LAB_TYPES.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => form.setFieldValue('type', t.value)}
                  className={cn(
                    'rounded-lg border px-2 py-2 text-xs font-medium transition-colors',
                    type === t.value
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border text-muted-foreground hover:bg-muted',
                  )}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          <TextInput
            key={form.key('location')}
            label="Location"
            placeholder="e.g. Hospital de Santa Maria"
            {...form.getInputProps('location')}
          />

          <Textarea
            key={form.key('notes')}
            label="Notes"
            placeholder="Optional notes..."
            minRows={2}
            {...form.getInputProps('notes')}
          />

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium leading-none">Markers</p>
              <button
                type="button"
                onClick={addRow}
                className="flex items-center gap-1 text-xs text-primary hover:underline"
              >
                <Plus className="size-3.5" />
                Add row
              </button>
            </div>

            {rows.map((row) => (
              <div
                key={row.id}
                className="space-y-2 rounded-lg border border-border bg-muted/20 p-3"
              >
                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">Marker</p>
                    <MarkerPicker
                      value={row.display_name || row.canonical_name}
                      onSelect={(canonical, id) =>
                        updateRow(row.id, {
                          canonical_name: canonical,
                          catalog_id: id,
                          display_name: row.display_name || canonical,
                        })
                      }
                    />
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">Display name</p>
                    <TextInput
                      value={row.display_name}
                      onChange={(e) => updateRow(row.id, { display_name: e.currentTarget.value })}
                      placeholder="e.g. Hemoglobin"
                      className="text-sm"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-4 gap-2">
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">Value</p>
                    <NumberInput
                      value={row.value}
                      onChange={(value) => updateRow(row.id, { value: value === '' ? '' : String(value) })}
                      placeholder="15.5"
                      className="text-sm"
                    />
                  </div>
                  {!row.value && (
                    <div className="space-y-1">
                      <p className="text-xs text-muted-foreground">Value text</p>
                      <TextInput
                        value={row.value_text}
                        onChange={(e) => updateRow(row.id, { value_text: e.currentTarget.value })}
                        placeholder="Negative"
                        className="text-sm"
                      />
                    </div>
                  )}
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">Unit</p>
                    <TextInput
                      value={row.unit}
                      onChange={(e) => updateRow(row.id, { unit: e.currentTarget.value })}
                      placeholder="g/dL"
                      className="text-sm"
                    />
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">Ref low</p>
                    <NumberInput
                      value={row.ref_low}
                      onChange={(value) => updateRow(row.id, { ref_low: value === '' ? '' : String(value) })}
                      placeholder="13.7"
                      className="text-sm"
                    />
                  </div>
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground">Ref high</p>
                    <NumberInput
                      value={row.ref_high}
                      onChange={(value) => updateRow(row.id, { ref_high: value === '' ? '' : String(value) })}
                      placeholder="17.2"
                      className="text-sm"
                    />
                  </div>
                </div>

                <div className="flex items-end justify-between gap-2">
                  <div className="flex-1 space-y-1">
                    <p className="text-xs text-muted-foreground">Ref text (optional)</p>
                    <TextInput
                      value={row.ref_text}
                      onChange={(e) => updateRow(row.id, { ref_text: e.currentTarget.value })}
                      placeholder="e.g. >60, Negative"
                      className="text-sm"
                    />
                  </div>
                  <button
                    type="button"
                    onClick={() => removeRow(row.id)}
                    className="mb-0.5 flex size-8 items-center justify-center rounded-lg border border-border text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                  >
                    <Trash2 className="size-3.5" />
                  </button>
                </div>
              </div>
            ))}

            {rows.length === 0 && (
              <p className="py-2 text-center text-xs text-muted-foreground">
                No markers added yet.
              </p>
            )}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? 'Saving...' : isEdit ? 'Save changes' : 'Add lab'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

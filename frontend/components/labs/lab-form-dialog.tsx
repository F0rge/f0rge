'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { Plus, Trash2 } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useCreateLab, useUpdateLab } from '@/lib/api/hooks'
import { MarkerPicker } from './marker-picker'
import { cn } from '@/lib/utils'
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

function todayStr(): string {
  return new Date().toISOString().split('T')[0]
}

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

  const initDate = prefill?.lab.lab_date ?? lab?.lab_date ?? todayStr()
  const initName = prefill?.lab.name ?? lab?.name ?? ''
  const initType: LabType = prefill?.lab.type ?? lab?.type ?? 'blood'
  const initLocation = prefill?.lab.lab_location ?? lab?.lab_location ?? ''
  const initNotes = prefill?.lab.notes ?? lab?.notes ?? ''
  const initRows = prefill ? prefillRows(prefill) : lab ? labToRows(lab) : [emptyRow()]

  const [date, setDate] = useState(initDate)
  const [name, setName] = useState(initName)
  const [type, setType] = useState<LabType>(initType)
  const [location, setLocation] = useState(initLocation)
  const [notes, setNotes] = useState(initNotes)
  const [rows, setRows] = useState<MarkerRow[]>(initRows)

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

  function buildMarkers(): LabMarkerCreate[] {
    return rows
      .filter((r) => r.canonical_name.trim() && r.display_name.trim())
      .map((r) => ({
        catalog_id: r.catalog_id ?? 0,
        canonical_name: r.canonical_name.trim(),
        display_name: r.display_name.trim(),
        value: r.value !== '' ? parseFloat(r.value) : null,
        value_text: r.value_text.trim() || null,
        unit: r.unit.trim() || null,
        ref_low: r.ref_low !== '' ? parseFloat(r.ref_low) : null,
        ref_high: r.ref_high !== '' ? parseFloat(r.ref_high) : null,
        ref_text: r.ref_text.trim() || null,
      }))
  }

  async function handleSubmit() {
    if (!date) { toast.error('Date is required'); return }
    if (!name.trim()) { toast.error('Name is required'); return }

    const markers = buildMarkers()
    const payload = {
      lab_date: date,
      name: name.trim(),
      type,
      lab_location: location.trim() || null,
      notes: notes.trim() || null,
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
    } catch {
      toast.error(isEdit ? 'Failed to update lab' : 'Failed to add lab')
    }
  }

  const isPending = createLab.isPending || updateLab.isPending

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? 'Edit Lab' : prefill ? 'Confirm Extracted Lab' : 'Add Lab'}
          </DialogTitle>
        </DialogHeader>

        {extractionMeta && (
          <div className="rounded-lg border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
            Extracted by {extractionMeta.model} &middot; confidence{' '}
            {Math.round(extractionMeta.confidence * 100)}% &middot; attempt
            {extractionMeta.attempts > 1 ? `s ${extractionMeta.attempts}` : ' 1'}
          </div>
        )}

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="lab-date">Date</Label>
              <Input
                id="lab-date"
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="lab-name">Name</Label>
              <Input
                id="lab-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Complete Blood Count"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Type</Label>
            <div className="grid grid-cols-4 gap-1.5">
              {LAB_TYPES.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => setType(t.value)}
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

          <div className="space-y-1.5">
            <Label htmlFor="lab-location">Location</Label>
            <Input
              id="lab-location"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="e.g. Hospital de Santa Maria"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="lab-notes">Notes</Label>
            <Textarea
              id="lab-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional notes..."
              rows={2}
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>Markers</Label>
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
                    <Label className="text-xs">Marker</Label>
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
                    <Label className="text-xs">Display name</Label>
                    <Input
                      value={row.display_name}
                      onChange={(e) => updateRow(row.id, { display_name: e.target.value })}
                      placeholder="e.g. Hemoglobin"
                      className="text-sm"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-4 gap-2">
                  <div className="space-y-1">
                    <Label className="text-xs">Value</Label>
                    <Input
                      type="number"
                      value={row.value}
                      onChange={(e) => updateRow(row.id, { value: e.target.value })}
                      placeholder="15.5"
                      className="text-sm"
                    />
                  </div>
                  {!row.value && (
                    <div className="space-y-1">
                      <Label className="text-xs">Value text</Label>
                      <Input
                        value={row.value_text}
                        onChange={(e) => updateRow(row.id, { value_text: e.target.value })}
                        placeholder="Negative"
                        className="text-sm"
                      />
                    </div>
                  )}
                  <div className="space-y-1">
                    <Label className="text-xs">Unit</Label>
                    <Input
                      value={row.unit}
                      onChange={(e) => updateRow(row.id, { unit: e.target.value })}
                      placeholder="g/dL"
                      className="text-sm"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Ref low</Label>
                    <Input
                      type="number"
                      value={row.ref_low}
                      onChange={(e) => updateRow(row.id, { ref_low: e.target.value })}
                      placeholder="13.7"
                      className="text-sm"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Ref high</Label>
                    <Input
                      type="number"
                      value={row.ref_high}
                      onChange={(e) => updateRow(row.id, { ref_high: e.target.value })}
                      placeholder="17.2"
                      className="text-sm"
                    />
                  </div>
                </div>

                <div className="flex items-end justify-between gap-2">
                  <div className="flex-1 space-y-1">
                    <Label className="text-xs">Ref text (optional)</Label>
                    <Input
                      value={row.ref_text}
                      onChange={(e) => updateRow(row.id, { ref_text: e.target.value })}
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
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={isPending}>
            {isPending ? 'Saving...' : isEdit ? 'Save changes' : 'Add lab'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

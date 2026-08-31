'use client'

import { Button } from '@f0rge/ui'
import { cn } from '@f0rge/ui'
import { LabAttachment } from './lab-attachment'
import { MarkerSparkline } from './marker-sparkline'
import type { Lab, LabType } from '@/lib/api/types'
import { labFlagClass, statusPill } from '@/lib/ui/status'

const FLAG_CLASSES = labFlagClass

const TYPE_LABELS: Record<LabType, string> = {
  blood: 'Blood',
  breath: 'Breath',
  imaging: 'Imaging',
  microbiology: 'Microbiology',
  allergy: 'Allergy',
  comprehensive: 'Comprehensive',
  other: 'Other',
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
}

function formatRefRange(refLow: number | null, refHigh: number | null, refText: string | null): string {
  if (refLow !== null && refHigh !== null) return `${refLow} – ${refHigh}`
  if (refLow !== null) return `> ${refLow}`
  if (refHigh !== null) return `< ${refHigh}`
  if (refText) return refText
  return '—'
}

interface LabDetailContentProps {
  lab: Lab
  confirmDelete: boolean
  deletePending: boolean
  onDelete: () => void
  onEdit: () => void
}

function MarkerMobileCard({
  marker,
}: {
  marker: Lab['markers'][number]
}) {
  return (
    <div className="space-y-2 rounded-lg border border-border/60 p-3 text-sm">
      <div className="flex items-start justify-between gap-2">
        <p className="break-words font-medium">{marker.display_name}</p>
        <span
          className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${FLAG_CLASSES[marker.flag] ?? FLAG_CLASSES.unknown}`}
        >
          {marker.flag}
        </span>
      </div>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
        <div>
          <dt className="text-muted-foreground">Value</dt>
          <dd className="tabular-nums">
            {marker.value !== null ? marker.value : marker.value_text ?? '—'}
          </dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Unit</dt>
          <dd className="break-words">{marker.unit ?? '—'}</dd>
        </div>
        <div className="col-span-2">
          <dt className="text-muted-foreground">Ref range</dt>
          <dd className="break-words">
            {formatRefRange(marker.ref_low, marker.ref_high, marker.ref_text)}
          </dd>
        </div>
        <div className="col-span-2">
          <dt className="mb-1 text-muted-foreground">Trend</dt>
          <dd>
            <MarkerSparkline canonicalName={marker.canonical_name} />
          </dd>
        </div>
      </dl>
    </div>
  )
}

export function LabDetailContent({
  lab,
  confirmDelete,
  deletePending,
  onDelete,
  onEdit,
}: LabDetailContentProps) {
  return (
    <div className="min-w-0 space-y-4 overflow-x-hidden">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <h2 className="break-words text-lg font-semibold">{lab.name}</h2>
          <p className="mt-0.5 break-words text-sm text-muted-foreground">
            {formatDate(lab.lab_date)} &middot; {TYPE_LABELS[lab.type] ?? lab.type}
            {lab.lab_location && ` · ${lab.lab_location}`}
          </p>
        </div>
        {lab.review_status === 'needs_review' && (
          <span className={cn('shrink-0 rounded-full px-2 py-0.5 text-xs font-medium', statusPill.warn)}>
            Needs review
          </span>
        )}
      </div>

      {lab.notes && (
        <p className="break-words text-sm text-muted-foreground">{lab.notes}</p>
      )}

      <LabAttachment lab={lab} />

      {lab.extraction_model && (
        <div className="break-words text-xs text-muted-foreground">
          Extracted by {lab.extraction_model}
          {lab.extraction_confidence !== null &&
            ` (confidence ${Math.round(lab.extraction_confidence * 100)}%)`}
        </div>
      )}

      {lab.markers.length > 0 ? (
        <>
          <div className="space-y-2 sm:hidden">
            {lab.markers.map((marker) => (
              <MarkerMobileCard key={marker.id} marker={marker} />
            ))}
          </div>
          <div className="hidden overflow-x-auto sm:block">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted-foreground">
                  <th className="pb-1.5 pr-3 font-medium">Marker</th>
                  <th className="pb-1.5 pr-3 font-medium">Flag</th>
                  <th className="pb-1.5 pr-3 font-medium">Value</th>
                  <th className="pb-1.5 pr-3 font-medium">Unit</th>
                  <th className="pb-1.5 pr-3 font-medium">Ref range</th>
                  <th className="pb-1.5 font-medium">Trend</th>
                </tr>
              </thead>
              <tbody>
                {lab.markers.map((marker) => (
                  <tr
                    key={marker.id}
                    className="border-b border-border/50 last:border-0"
                  >
                    <td className="py-2 pr-3 font-medium">{marker.display_name}</td>
                    <td className="py-2 pr-3">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${FLAG_CLASSES[marker.flag] ?? FLAG_CLASSES.unknown}`}>
                        {marker.flag}
                      </span>
                    </td>
                    <td className="py-2 pr-3 tabular-nums">
                      {marker.value !== null
                        ? marker.value
                        : marker.value_text ?? '—'}
                    </td>
                    <td className="py-2 pr-3 text-muted-foreground">
                      {marker.unit ?? '—'}
                    </td>
                    <td className="py-2 pr-3 text-muted-foreground">
                      {formatRefRange(marker.ref_low, marker.ref_high, marker.ref_text)}
                    </td>
                    <td className="py-2">
                      <MarkerSparkline canonicalName={marker.canonical_name} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <p className="py-4 text-center text-sm text-muted-foreground">No markers recorded.</p>
      )}

      <div className="flex gap-2 pt-2">
        <Button
          variant="destructive"
          size="sm"
          onClick={onDelete}
          disabled={deletePending}
          className="mr-auto"
        >
          {confirmDelete ? 'Confirm delete' : 'Delete'}
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={onEdit}
        >
          Edit
        </Button>
      </div>
    </div>
  )
}

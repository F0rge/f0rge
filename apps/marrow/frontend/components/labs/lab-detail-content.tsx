'use client'

import { Button } from '@f0rge/ui'
import { MarkerSparkline } from './marker-sparkline'
import type { Lab, MarkerFlag, LabType } from '@/lib/api/types'

const FLAG_CLASSES: Record<MarkerFlag, string> = {
  normal: 'bg-muted text-muted-foreground',
  low: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  high: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
  abnormal: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
  unknown: 'bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-400',
}

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

export function LabDetailContent({
  lab,
  confirmDelete,
  deletePending,
  onDelete,
  onEdit,
}: LabDetailContentProps) {
  const filename = lab.attachment_path
    ? lab.attachment_path.split('/').pop() ?? lab.attachment_path
    : null

  return (
    <>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="truncate text-lg font-semibold">{lab.name}</h2>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {formatDate(lab.lab_date)} &middot; {TYPE_LABELS[lab.type] ?? lab.type}
            {lab.lab_location && ` &middot; ${lab.lab_location}`}
          </p>
        </div>
        {lab.review_status === 'needs_review' && (
          <span className="shrink-0 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900/30 dark:text-amber-400">
            Needs review
          </span>
        )}
      </div>

      {lab.notes && (
        <p className="text-sm text-muted-foreground">{lab.notes}</p>
      )}

      {filename && (
        <div className="text-xs text-muted-foreground">
          Source: {filename}
        </div>
      )}

      {lab.extraction_model && (
        <div className="text-xs text-muted-foreground">
          Extracted by {lab.extraction_model}
          {lab.extraction_confidence !== null &&
            ` (confidence ${Math.round(lab.extraction_confidence * 100)}%)`}
        </div>
      )}

      {lab.markers.length > 0 ? (
        <div className="overflow-x-auto">
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
    </>
  )
}

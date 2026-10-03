'use client'

import {
  Badge,
  Button,
  Item,
  ItemContent,
  ItemGroup,
  ItemHeader,
  ItemTitle,
  cn,
} from '@f0rge/ui'
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
  pdfPreview?: boolean
}

function MarkerRow({ marker }: { marker: Lab['markers'][number] }) {
  const value =
    marker.value !== null ? String(marker.value) : marker.value_text ?? '—'

  return (
    <Item variant="outline" size="sm" className="rounded-xl bg-card">
      <ItemContent>
        <ItemHeader>
          <ItemTitle className="break-words">{marker.display_name}</ItemTitle>
          <Badge className={FLAG_CLASSES[marker.flag] ?? FLAG_CLASSES.unknown}>
            {marker.flag}
          </Badge>
        </ItemHeader>
        <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <div>
            <dt>Value</dt>
            <dd className="tabular-nums text-foreground">{value}</dd>
          </div>
          <div>
            <dt>Unit</dt>
            <dd className="break-words text-foreground">{marker.unit ?? '—'}</dd>
          </div>
          <div className="col-span-2">
            <dt>Ref range</dt>
            <dd className="break-words text-foreground">
              {formatRefRange(marker.ref_low, marker.ref_high, marker.ref_text)}
            </dd>
          </div>
          <div className="col-span-2">
            <dt className="mb-1">Trend</dt>
            <dd>
              <MarkerSparkline canonicalName={marker.canonical_name} />
            </dd>
          </div>
        </dl>
      </ItemContent>
    </Item>
  )
}

export function LabDetailContent({
  lab,
  confirmDelete,
  deletePending,
  onDelete,
  onEdit,
  pdfPreview = false,
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

      <LabAttachment lab={lab} pdfPreview={pdfPreview} />

      {lab.extraction_model && (
        <div className="break-words text-xs text-muted-foreground">
          Extracted by {lab.extraction_model}
          {lab.extraction_confidence !== null &&
            ` (confidence ${Math.round(lab.extraction_confidence * 100)}%)`}
        </div>
      )}

      {lab.markers.length > 0 ? (
        <ItemGroup className="gap-2">
          {lab.markers.map((marker) => (
            <MarkerRow key={marker.id} marker={marker} />
          ))}
        </ItemGroup>
      ) : (
        <p className="py-4 text-center text-sm text-muted-foreground">No markers recorded.</p>
      )}

      <div className="flex min-w-0 gap-2 pt-2">
        <Button
          variant="destructive"
          onClick={onDelete}
          disabled={deletePending}
          className="mr-auto min-h-[44px]"
        >
          {confirmDelete ? 'Confirm delete' : 'Delete'}
        </Button>
        <Button
          variant="outline"
          onClick={onEdit}
          className="min-h-[44px]"
        >
          Edit
        </Button>
      </div>
    </div>
  )
}

'use client'

import { use } from 'react'
import Link from 'next/link'
import { ArrowLeft, Pencil, Loader2 } from 'lucide-react'
import { useEntry } from '@/lib/api/hooks'
import type { Entry } from '@/lib/api/types'

function formatDisplayDate(dateStr: string): string {
  const date = new Date(dateStr + 'T00:00:00')
  return date.toLocaleDateString('en-GB', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

function getOverallLabel(overall: number): string {
  switch (overall) {
    case 1: return 'Very Poor'
    case 2: return 'Poor'
    case 3: return 'Standard'
    case 4: return 'Good'
    case 5: return 'Very Good'
    default: return 'Unknown'
  }
}

function getOverallBadgeClass(overall: number): string {
  if (overall >= 4) return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
  if (overall === 3) return 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400'
  return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
}

function getBloatingLabel(v: number): string {
  return ['None', 'Mild', 'Moderate', 'Severe'][v] ?? 'Unknown'
}

function getJointPainLabel(v: number): string {
  return ['None', 'Mild', 'Moderate', 'Severe'][v] ?? 'Unknown'
}

function getNeuroLabel(v: number): string {
  if (v === -1) return 'Worse'
  if (v === 1) return 'Better'
  return 'Baseline'
}

function getSleepLabel(v: number): string {
  return ['', 'Poor', 'OK', 'Good'][v] ?? 'Unknown'
}

function getStressLabel(v: number): string {
  return ['', 'Low', 'Medium', 'High'][v] ?? 'Unknown'
}

function getDietLabel(v: string): string {
  switch (v) {
    case 'normal': return 'Normal'
    case 'high-histamine': return 'High-histamine'
    case 'high-fodmap': return 'High-FODMAP'
    case 'both': return 'Both'
    default: return v
  }
}

const BRISTOL_HINTS: Record<number, string> = {
  1: 'Type 1 - separate hard lumps',
  2: 'Type 2 - lumpy sausage',
  3: 'Type 3 - sausage with cracks',
  4: 'Type 4 - smooth sausage (ideal)',
  5: 'Type 5 - soft blobs',
  6: 'Type 6 - mushy / fluffy',
  7: 'Type 7 - liquid',
}

function getStoolLabel(entry: Entry): string {
  const status =
    entry.stool_status ??
    (entry.stool_normal === false ? 'abnormal' : entry.stool_normal === true ? 'normal' : null)
  if (status === 'none') return 'No movement today'
  if (status === 'normal') return 'Normal'
  if (status === 'abnormal') {
    if (entry.bristol_type) return `Abnormal — ${BRISTOL_HINTS[entry.bristol_type] ?? `Bristol ${entry.bristol_type}`}`
    if (entry.stool_type) return `Abnormal (${entry.stool_type})`
    return 'Abnormal'
  }
  return 'Not recorded'
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-2">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  )
}

function EntryDetail({ entry }: { entry: Entry }) {
  return (
    <div className="rounded-xl border border-border bg-card">
      <div className="border-b border-border px-4 py-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">Overall</span>
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${getOverallBadgeClass(entry.overall)}`}>
            {getOverallLabel(entry.overall)}
          </span>
        </div>
      </div>
      <div className="divide-y divide-border px-4">
        <DetailRow label="Bloating" value={getBloatingLabel(entry.bloating)} />
        <DetailRow label="Stool" value={getStoolLabel(entry)} />
        <DetailRow label="Joint pain" value={getJointPainLabel(entry.joint_pain)} />
        <DetailRow label="Neuro" value={getNeuroLabel(entry.neuro)} />
        <DetailRow label="Sleep" value={getSleepLabel(entry.sleep_quality)} />
        <DetailRow label="Stress" value={getStressLabel(entry.stress)} />
        <DetailRow label="Diet risk" value={getDietLabel(entry.diet_risk)} />
        <DetailRow label="Supplements" value={entry.supplements.charAt(0).toUpperCase() + entry.supplements.slice(1)} />
        <DetailRow label="Sick" value={entry.sick ? 'Yes' : 'No'} />
        <DetailRow label="Hot shower" value={entry.hot_shower ? 'Yes' : 'No'} />
        {entry.entry_time && (
          <DetailRow
            label="Logged at"
            value={`${new Date(entry.entry_time).toLocaleString('en-GB', { hour: '2-digit', minute: '2-digit' })}${entry.period_of_day ? ` (${entry.period_of_day})` : ''}`}
          />
        )}
      </div>

      {entry.notes && (
        <div className="border-t border-border px-4 py-3">
          <p className="mb-1 text-xs font-medium text-muted-foreground">Notes</p>
          <p className="text-sm">{entry.notes}</p>
        </div>
      )}

      {entry.photos && entry.photos.length > 0 && (
        <div className="border-t border-border px-4 py-3">
          <p className="mb-2 text-xs font-medium text-muted-foreground">Photos</p>
          <div className="grid grid-cols-2 gap-2">
            {entry.photos.map((photo) => (
              <div key={photo.id} className="overflow-hidden rounded-lg">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`/api/v1/photos/${photo.id}/file`}
                  alt={photo.label || `Photo ${photo.id}`}
                  className="aspect-square w-full object-cover"
                />
                {photo.label && (
                  <p className="bg-muted px-2 py-1 text-xs text-muted-foreground">{photo.label}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function HistoryDatePage({ params }: { params: Promise<{ date: string }> }) {
  const { date } = use(params)
  const { data: entry, isLoading, isError } = useEntry(date)

  return (
    <div className="mx-auto w-full max-w-lg p-4">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <Link
            href="/history"
            className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
            Back
          </Link>
          <h1 className="text-xl font-semibold tracking-tight">{formatDisplayDate(date)}</h1>
        </div>
        {entry && (
          <Link
            href={`/checkin/${date}`}
            className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm font-medium transition-colors hover:bg-muted"
          >
            <Pencil className="size-3.5" />
            Edit
          </Link>
        )}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      ) : isError || !entry ? (
        <div className="rounded-xl border border-border bg-card px-4 py-8 text-center">
          <p className="text-sm text-muted-foreground">No entry for this date.</p>
          <Link
            href={`/checkin/${date}`}
            className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
          >
            Create one
          </Link>
        </div>
      ) : (
        <EntryDetail entry={entry} />
      )}
    </div>
  )
}

'use client'

import { use, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Pencil, Loader2, Pill } from 'lucide-react'
import { useEntry, useUpdatePhotoMealTime, useMedicationCatalog, useSymptomCatalog } from '@/lib/api/hooks'
import { MealIconThumb, photoHasImage, photoThumbSrc } from '@/components/checkin/meal-icon-thumb'
import { MealTimeChips } from '@/components/checkin/meal-time-chips'
import { PhotoAnalysisDisclosure } from '@/components/history/photo-analysis-disclosure'
import { PageShell } from '@/components/layout/page-shell'
import { PageHeader } from '@/components/layout/page-header'
import type { Entry, Photo } from '@/lib/api/types'
import { getOverallBadgeClass, getScaleLabel } from '@/lib/checkin/scale-labels'

function formatDisplayDate(dateStr: string): string {
  const date = new Date(dateStr + 'T00:00:00')
  return date.toLocaleDateString('en-GB', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

// bloating is 0-3 in every schema version — unaffected by v4.
function getBloatingLabel(v: number): string {
  return ['None', 'Mild', 'Moderate', 'Severe'][v] ?? 'Unknown'
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

function formatHHMM(isoStr: string): string {
  const d = new Date(isoStr)
  return d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false })
}

function PhotoWithMealTime({ photo }: { photo: Photo }) {
  const updateMealTime = useUpdatePhotoMealTime()
  const [optimisticMealTime, setOptimisticMealTime] = useState<string | null>(photo.meal_time)

  const handleChange = (d: Date) => {
    const iso = d.toISOString()
    setOptimisticMealTime(iso)
    updateMealTime.mutate({ photoId: photo.id, mealTime: iso })
  }

  const chipValue = optimisticMealTime ? new Date(optimisticMealTime) : null

  return (
    <div className="flex flex-col gap-2">
      <div className="overflow-hidden rounded-lg border border-border">
        {photoHasImage(photo) ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={photoThumbSrc(photo.id)}
            alt={photo.label || `Photo ${photo.id}`}
            className="aspect-square w-full object-cover"
          />
        ) : (
          <div className="relative flex aspect-square w-full items-center justify-center bg-muted">
            <MealIconThumb
              iconKey={photo.icon_key ?? 'bowl'}
              size="lg"
              className="size-24 rounded-2xl"
            />
          </div>
        )}
        {photo.label && (
          <p className="bg-muted px-2 py-1 text-xs text-muted-foreground">{photo.label}</p>
        )}
        <div className="px-2 pb-2 pt-1.5">
          {optimisticMealTime && (
            <p className="mb-1 text-xs text-muted-foreground">
              Meal time: {formatHHMM(optimisticMealTime)}
            </p>
          )}
          <MealTimeChips value={chipValue} onChange={handleChange} />
        </div>
      </div>
      <PhotoAnalysisDisclosure photoId={photo.id} photoLabel={photo.label} photo={photo} />
    </div>
  )
}

function MedicationsSection({ medications }: { medications: Entry['medications'] }) {
  const { data: catalog = [] } = useMedicationCatalog(true)
  const labelFor = (key: string) => catalog.find((m) => m.key === key)?.label ?? key

  if (medications.length === 0) return null

  return (
    <div className="border-t border-border px-4 py-3">
      <p className="mb-2 text-xs font-medium text-muted-foreground">Medications</p>
      <div className="space-y-2">
        {medications.map((intake, index) => (
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
          </div>
        ))}
      </div>
    </div>
  )
}

function SymptomsSection({ symptoms }: { symptoms: Record<string, number> }) {
  const { data: catalog = [] } = useSymptomCatalog(true)
  const labelFor = (key: string) => catalog.find((s) => s.key === key)?.label ?? key
  const entries = Object.entries(symptoms).filter(([, severity]) => severity > 0)

  if (entries.length === 0) return null

  return (
    <div className="border-t border-border px-4 py-3">
      <p className="mb-2 text-xs font-medium text-muted-foreground">Symptoms</p>
      <div className="space-y-2">
        {entries.map(([key, severity]) => (
          <DetailRow
            key={key}
            label={labelFor(key)}
            value={`${severity}/10`}
          />
        ))}
      </div>
    </div>
  )
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-border py-2 last:border-b-0">
      <span className="shrink-0 text-sm text-muted-foreground">{label}</span>
      <span className="min-w-0 break-words text-right text-sm font-medium">{value}</span>
    </div>
  )
}

function EntryDetail({ entry }: { entry: Entry }) {
  return (
    <div className="rounded-xl border border-border bg-card">
      <div className="border-b border-border px-4 py-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">Overall</span>
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${getOverallBadgeClass(entry.overall, entry.schema_version)}`}>
            {getScaleLabel('overall', entry.overall, entry.schema_version)}
          </span>
        </div>
      </div>
      <div className="grid grid-cols-1 px-4 lg:grid-cols-2 lg:gap-x-6">
        <DetailRow label="Bloating" value={getBloatingLabel(entry.bloating)} />
        <DetailRow label="Stool" value={getStoolLabel(entry)} />
        {entry.stool_completeness && (
          <DetailRow
            label="Stool completeness"
            value={entry.stool_completeness === 'complete' ? 'Complete' : 'Incomplete'}
          />
        )}
        <DetailRow label="Sleep" value={getScaleLabel('sleep_quality', entry.sleep_quality, entry.schema_version)} />
        <DetailRow label="Stress" value={getScaleLabel('stress', entry.stress, entry.schema_version)} />
        <DetailRow
          label="Diet risk"
          value={
            entry.effective_flags && entry.effective_flags.length > 0
              ? entry.effective_flags.join(', ')
              : 'Normal'
          }
        />
        <DetailRow label="Supplements" value={entry.supplements.charAt(0).toUpperCase() + entry.supplements.slice(1)} />
        <DetailRow label="Sick" value={entry.sick ? 'Yes' : 'No'} />
        <DetailRow label="Hot shower" value={entry.hot_shower ? 'Yes' : 'No'} />
        {entry.entry_time && (
          <DetailRow
            label="Last logged at"
            value={`${new Date(entry.entry_time).toLocaleString('en-GB', { hour: '2-digit', minute: '2-digit' })}${entry.period_of_day ? ` (${entry.period_of_day})` : ''}`}
          />
        )}
      </div>

      <SymptomsSection symptoms={entry.symptoms_json ?? {}} />

      {entry.notes && (
        <div className="border-t border-border px-4 py-3">
          <p className="mb-1 text-xs font-medium text-muted-foreground">Notes</p>
          <p className="text-sm">{entry.notes}</p>
        </div>
      )}

      <MedicationsSection medications={entry.medications} />

      {entry.photos && entry.photos.length > 0 && (
        <div className="border-t border-border px-4 py-3">
          <p className="mb-2 text-xs font-medium text-muted-foreground">Photos</p>
          <div className="grid grid-cols-2 gap-2 lg:grid-cols-3">
            {entry.photos.map((photo) => (
              <PhotoWithMealTime key={photo.id} photo={photo} />
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
    <PageShell>
      <PageHeader
        leading={
          <Link
            href="/history"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
            Back
          </Link>
        }
        title={formatDisplayDate(date)}
        actions={
          entry ? (
            <Link
              href={`/checkin/${date}`}
              className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm font-medium transition-colors hover:bg-muted"
            >
              <Pencil className="size-3.5" />
              Edit
            </Link>
          ) : undefined
        }
      />

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
    </PageShell>
  )
}

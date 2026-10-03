'use client'

import type { Entry } from '@/lib/api/types'
import { useSymptomCatalog } from '@/lib/api/hooks'
import { getOverallBadgeClass, getScaleLabel } from '@/lib/checkin/scale-labels'

interface EntryCardProps {
  entry: Entry
  onClick: () => void
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr + 'T00:00:00')
  return date.toLocaleDateString('en-GB', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

function getSummary(entry: Entry, symptomLabels: Map<string, string>): string {
  const parts: string[] = []
  if ((entry.bloating ?? 0) > 0) {
    const level = entry.bloating === 1 ? 'mild' : entry.bloating === 2 ? 'moderate' : 'severe'
    parts.push(`${level} bloating`)
  }
  const stool = entry.stool_status ?? (entry.stool_normal === false ? 'abnormal' : entry.stool_normal === true ? 'normal' : null)
  if (stool === 'abnormal') {
    parts.push(entry.bristol_type ? `stool B${entry.bristol_type}` : 'abnormal stool')
  } else if (stool === 'none') {
    parts.push('no stool')
  }

  for (const [key, severity] of Object.entries(entry.symptoms_json ?? {})) {
    if (severity > 0) {
      const label = symptomLabels.get(key) ?? key.replace(/_/g, ' ')
      parts.push(`${label} ${severity}/10`)
    }
  }

  if (entry.sick) parts.push('sick')
  if (entry.hot_shower) parts.push('hot shower')
  if (parts.length === 0) return 'Baseline day'
  return parts.join(', ')
}

export function EntryCard({ entry, onClick }: EntryCardProps) {
  const { data: catalog = [] } = useSymptomCatalog(false)
  const symptomLabels = new Map(catalog.map((item) => [item.key, item.label]))

  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full rounded-[var(--radius)] border border-border bg-card p-5 text-left transition-colors hover:bg-muted/40"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium text-foreground">{formatDate(entry.date)}</span>
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${getOverallBadgeClass(entry.overall, entry.schema_version)}`}>
          {getScaleLabel('overall', entry.overall, entry.schema_version)}
        </span>
      </div>
      <p className="mt-1.5 text-sm text-muted-foreground">{getSummary(entry, symptomLabels)}</p>
    </button>
  )
}

'use client'

import type { Entry } from '@/lib/api/types'
import { getOverallTier, getScaleLabel, type ScaleTier } from '@/lib/checkin/scale-labels'

interface EntryCardProps {
  entry: Entry
  onClick: () => void
}

const OVERALL_BADGE_CLASS: Record<ScaleTier, string> = {
  good: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
  neutral: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
  poor: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr + 'T00:00:00')
  return date.toLocaleDateString('en-GB', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })
}

function getSummary(entry: Entry): string {
  const parts: string[] = []
  if (entry.bloating > 0) {
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
      parts.push(`${key.replace(/_/g, ' ')} ${severity}/10`)
    }
  }

  if (entry.sick) parts.push('sick')
  if (entry.hot_shower) parts.push('hot shower')
  if (parts.length === 0) return 'Baseline day'
  return parts.join(', ')
}

export function EntryCard({ entry, onClick }: EntryCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full rounded-xl border border-border bg-card p-4 text-left transition-colors hover:bg-muted/50"
    >
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">{formatDate(entry.date)}</span>
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${OVERALL_BADGE_CLASS[getOverallTier(entry.overall, entry.schema_version)]}`}>
          {getScaleLabel('overall', entry.overall, entry.schema_version)}
        </span>
      </div>
      <p className="mt-1 text-sm text-muted-foreground">{getSummary(entry)}</p>
    </button>
  )
}

'use client'

import type { Entry } from '@/lib/api/types'

interface EntryCardProps {
  entry: Entry
  onClick: () => void
}

function getOverallLabel(overall: number): string {
  switch (overall) {
    case 1: return 'Very Poor'
    case 2: return 'Standard'
    case 3: return 'Very Good'
    default: return 'Unknown'
  }
}

function getOverallBadgeClass(overall: number): string {
  if (overall === 3) return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
  if (overall === 2) return 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400'
  return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
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
  if (!entry.stool_normal) parts.push('abnormal stool')
  if (entry.joint_pain > 0) {
    const level = entry.joint_pain === 1 ? 'mild' : entry.joint_pain === 2 ? 'moderate' : 'severe'
    parts.push(`${level} joint pain`)
  }
  if (entry.neuro === -1) parts.push('neuro worse')
  if (entry.neuro === 1) parts.push('neuro better')
  if (entry.sick) parts.push('sick')
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
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${getOverallBadgeClass(entry.overall)}`}>
          {getOverallLabel(entry.overall)}
        </span>
      </div>
      <p className="mt-1 text-sm text-muted-foreground">{getSummary(entry)}</p>
    </button>
  )
}

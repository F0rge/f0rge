'use client'

import type { Lab, LabType } from '@/lib/api/types'
import { cn, formatDisplayDate } from '@f0rge/ui'

interface LabCardProps {
  lab: Lab
  onClick: () => void
  selected?: boolean
}

const TYPE_CLASSES: Record<LabType, string> = {
  blood: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
  breath: 'bg-sky-100 text-sky-800 dark:bg-sky-900/30 dark:text-sky-400',
  imaging: 'bg-violet-100 text-violet-800 dark:bg-violet-900/30 dark:text-violet-400',
  microbiology: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
  allergy: 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
  comprehensive: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  other: 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400',
}

export function LabCard({ lab, onClick, selected = false }: LabCardProps) {
  const abnormalCount = lab.markers.filter(
    (m) => m.flag === 'low' || m.flag === 'high' || m.flag === 'abnormal',
  ).length

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'w-full rounded-xl border bg-card p-4 text-left transition-colors hover:bg-muted/50',
        selected ? 'border-primary ring-1 ring-primary/30' : 'border-border',
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="shrink-0">
          <p className="text-xs text-muted-foreground">{formatDisplayDate(lab.lab_date)}</p>
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="truncate text-sm font-medium">{lab.name}</span>
            <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${TYPE_CLASSES[lab.type] ?? TYPE_CLASSES.other}`}>
              {lab.type}
            </span>
          </div>
          {lab.lab_location && (
            <p className="mt-0.5 truncate text-xs text-muted-foreground">{lab.lab_location}</p>
          )}
        </div>

        <div className="flex shrink-0 flex-col items-end gap-1">
          <span className="text-xs text-muted-foreground">
            {lab.markers.length} marker{lab.markers.length !== 1 ? 's' : ''}
          </span>
          {abnormalCount > 0 && (
            <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800 dark:bg-red-900/30 dark:text-red-400">
              {abnormalCount} abnormal
            </span>
          )}
          {lab.review_status === 'needs_review' && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900/30 dark:text-amber-400">
              review
            </span>
          )}
        </div>
      </div>
    </button>
  )
}

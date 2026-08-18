'use client'

import type { Lab } from '@/lib/api/types'
import { cn, formatDisplayDate } from '@f0rge/ui'
import { labTypeClass, statusPill } from '@/lib/ui/status'

interface LabCardProps {
  lab: Lab
  onClick: () => void
  selected?: boolean
}

const TYPE_CLASSES = labTypeClass

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
            <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium', statusPill.destructive)}>
              {abnormalCount} abnormal
            </span>
          )}
          {lab.review_status === 'needs_review' && (
            <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium', statusPill.warn)}>
              review
            </span>
          )}
        </div>
      </div>
    </button>
  )
}

'use client'

import type { Treatment } from '@/lib/api/types'
import { cn, formatDisplayDate } from '@f0rge/ui'
import { getEndReasonLabel } from './end-reason'
import { statusPill, treatmentTypeClass } from '@/lib/ui/status'

interface TreatmentCardProps {
  treatment: Treatment
  onClick: () => void
  onDiscontinue: () => void
}

const TYPE_BADGE_CLASSES = treatmentTypeClass

function formatDateRange(treatment: Treatment): string {
  const startStr = formatDisplayDate(treatment.start_date)
  if (!treatment.end_date) return `${startStr} - ongoing`
  return `${startStr} - ${formatDisplayDate(treatment.end_date)}`
}

function dayCount(treatment: Treatment): string | null {
  if (!treatment.is_active) return null
  const start = new Date(treatment.start_date + 'T00:00:00')
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const days = Math.floor((today.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)) + 1
  return `Day ${days}`
}

export function TreatmentCard({ treatment, onClick, onDiscontinue }: TreatmentCardProps) {
  const badgeClass = TYPE_BADGE_CLASSES[treatment.type] ?? TYPE_BADGE_CLASSES.other
  const day = dayCount(treatment)
  // "Active" for the Discontinue action means no end_date at all — distinct
  // from the backend's `is_active` computed field, which stays true through
  // the end_date itself (so a just-discontinued treatment would otherwise
  // still show the action alongside its own "ended" badge).
  const notEnded = !treatment.end_date
  const ended = !!treatment.end_date && !!treatment.end_reason

  return (
    <div className="w-full rounded-xl border border-border bg-card transition-colors hover:bg-muted/50">
      <button type="button" onClick={onClick} className="w-full p-4 text-left">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="truncate text-sm font-medium">{treatment.name}</span>
              {treatment.is_active && (
                <span className={cn('shrink-0 rounded-full px-2 py-0.5 text-xs font-medium', statusPill.ok)}>
                  Active
                </span>
              )}
            </div>
            <p className="mt-0.5 text-sm text-muted-foreground">{formatDateRange(treatment)}</p>
            {treatment.dose && (
              <p className="mt-0.5 text-xs text-muted-foreground">{treatment.dose}</p>
            )}
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1">
            <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${badgeClass}`}>
              {treatment.type}
            </span>
            {day && (
              <span className="text-xs font-medium text-primary">{day}</span>
            )}
          </div>
        </div>
      </button>

      {notEnded && (
        <div className="border-t border-border/50 px-4 py-2">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              onDiscontinue()
            }}
            className="text-xs font-medium text-muted-foreground hover:text-destructive"
          >
            Discontinue
          </button>
        </div>
      )}

      {ended && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation()
            onDiscontinue()
          }}
          className="block w-full border-t border-border/50 px-4 py-2 text-left"
        >
          <span
            className={cn(
              'rounded-full px-2 py-0.5 text-xs font-medium',
              treatment.end_reason === 'completed' ? statusPill.ok : statusPill.warn,
            )}
          >
            {treatment.end_reason === 'completed'
              ? 'Completed'
              : `Discontinued · ${getEndReasonLabel(treatment.end_reason as string)}`}
          </span>
          {treatment.end_note && (
            <p className="mt-1 text-xs text-muted-foreground">{treatment.end_note}</p>
          )}
        </button>
      )}
    </div>
  )
}

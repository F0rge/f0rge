'use client'

import type { Treatment } from '@/lib/api/types'
import { formatDisplayDate } from '@f0rge/ui'
import { getEndReasonLabel } from './end-reason'

interface TreatmentCardProps {
  treatment: Treatment
  onClick: () => void
  onDiscontinue: () => void
}

const TYPE_BADGE_CLASSES: Record<string, string> = {
  antibiotic: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
  antimicrobial: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400',
  prescription: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
  intervention: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400',
  protocol: 'bg-teal-100 text-teal-800 dark:bg-teal-900/30 dark:text-teal-400',
  other: 'bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400',
}

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
                <span className="shrink-0 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800 dark:bg-green-900/30 dark:text-green-400">
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
            className={
              treatment.end_reason === 'completed'
                ? 'rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800 dark:bg-green-900/30 dark:text-green-400'
                : 'rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-900/30 dark:text-amber-400'
            }
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

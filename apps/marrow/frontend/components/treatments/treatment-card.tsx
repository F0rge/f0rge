'use client'

import type { Treatment } from '@/lib/api/types'
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardFooter,
  cn,
  formatDisplayDate,
} from '@f0rge/ui'
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
  const notEnded = !treatment.end_date
  const ended = !!treatment.end_date && !!treatment.end_reason

  return (
    <Card size="sm" className="overflow-hidden p-0 ring-1 ring-foreground/10">
      <button type="button" onClick={onClick} className="w-full text-left">
        <CardContent className="pt-4">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="truncate text-sm font-medium">{treatment.name}</span>
                {treatment.is_active && (
                  <Badge className={statusPill.ok}>Active</Badge>
                )}
              </div>
              <p className="mt-0.5 text-sm text-muted-foreground">{formatDateRange(treatment)}</p>
              {treatment.dose && (
                <p className="mt-0.5 text-xs text-muted-foreground">{treatment.dose}</p>
              )}
            </div>
            <div className="flex shrink-0 flex-col items-end gap-1">
              <Badge className={badgeClass}>{treatment.type}</Badge>
              {day && (
                <span className="text-xs font-medium text-primary">{day}</span>
              )}
            </div>
          </div>
        </CardContent>
      </button>

      {notEnded && (
        <CardFooter className="border-t border-border/50 py-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-auto px-0 text-xs font-medium text-muted-foreground hover:text-destructive"
            onClick={(e) => {
              e.stopPropagation()
              onDiscontinue()
            }}
          >
            Discontinue
          </Button>
        </CardFooter>
      )}

      {ended && (
        <CardFooter className="border-t border-border/50 py-2">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              onDiscontinue()
            }}
            className="w-full text-left"
          >
            <Badge
              className={cn(
                treatment.end_reason === 'completed' ? statusPill.ok : statusPill.warn,
              )}
            >
              {treatment.end_reason === 'completed'
                ? 'Completed'
                : `Discontinued · ${getEndReasonLabel(treatment.end_reason as string)}`}
            </Badge>
            {treatment.end_note && (
              <p className="mt-1 text-xs text-muted-foreground">{treatment.end_note}</p>
            )}
          </button>
        </CardFooter>
      )}
    </Card>
  )
}

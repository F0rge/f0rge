'use client'

import { useState, useMemo } from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import type { Treatment } from '@/lib/api/types'
import { cn } from '@/lib/utils'

interface TreatmentTimelineProps {
  treatments: Treatment[]
  onTreatmentClick: (treatment: Treatment) => void
}

const TYPE_BAR_CLASSES: Record<string, string> = {
  antibiotic: 'bg-red-400 dark:bg-red-500',
  antimicrobial: 'bg-orange-400 dark:bg-orange-500',
  prescription: 'bg-blue-400 dark:bg-blue-500',
  intervention: 'bg-purple-400 dark:bg-purple-500',
  protocol: 'bg-teal-400 dark:bg-teal-500',
  other: 'bg-gray-400 dark:bg-gray-500',
}

function addDays(date: Date, days: number): Date {
  const d = new Date(date)
  d.setDate(d.getDate() + days)
  return d
}

function daysBetween(a: Date, b: Date): number {
  return Math.round((b.getTime() - a.getTime()) / (1000 * 60 * 60 * 24))
}

function toDate(str: string): Date {
  return new Date(str + 'T00:00:00')
}

function formatMonthLabel(date: Date): string {
  return date.toLocaleDateString('en-GB', { month: 'short' })
}

export function TreatmentTimeline({ treatments, onTreatmentClick }: TreatmentTimelineProps) {
  const today = useMemo(() => {
    const d = new Date()
    d.setHours(0, 0, 0, 0)
    return d
  }, [])
  const [rangeStart, setRangeStart] = useState(() => {
    const activeStarts = treatments
      .filter((t) => t.end_date === null || toDate(t.end_date) >= today)
      .map((t) => toDate(t.start_date).getTime())
    if (activeStarts.length === 0) return addDays(today, -60)
    return addDays(new Date(Math.min(...activeStarts)), -7)
  })
  const rangeDays = 90
  const rangeEnd = useMemo(() => addDays(rangeStart, rangeDays - 1), [rangeStart])

  const todayOffset = daysBetween(rangeStart, today)

  const weekMarkers = useMemo(() => {
    const markers: { offset: number; label: string; isMonthStart: boolean }[] = []
    let d = new Date(rangeStart)
    for (let i = 0; i < rangeDays; i++) {
      if (d.getDate() === 1) {
        markers.push({
          offset: i,
          label: formatMonthLabel(d),
          isMonthStart: true,
        })
      } else if (d.getDay() === 1 && i > 0) {
        markers.push({ offset: i, label: '', isMonthStart: false })
      }
      d = addDays(d, 1)
    }
    return markers
  }, [rangeStart])

  const visibleTreatments = useMemo(
    () =>
      treatments.filter((t) => {
        const start = toDate(t.start_date)
        const end = t.end_date ? toDate(t.end_date) : today
        return start <= rangeEnd && end >= rangeStart
      }),
    [treatments, rangeStart, rangeEnd, today],
  )

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={() => setRangeStart((prev) => addDays(prev, -30))}
          className="flex size-8 items-center justify-center rounded-lg transition-colors hover:bg-muted"
        >
          <ChevronLeft className="size-4" />
        </button>
        <span className="text-xs text-muted-foreground">
          {rangeStart.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
          {' - '}
          {rangeEnd.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
        </span>
        <button
          type="button"
          onClick={() => setRangeStart((prev) => addDays(prev, 30))}
          className="flex size-8 items-center justify-center rounded-lg transition-colors hover:bg-muted"
        >
          <ChevronRight className="size-4" />
        </button>
      </div>

      {visibleTreatments.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">
          No treatments in this date range.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border">
          <div className="min-w-[500px]">
            <div className="relative flex h-6 border-b border-border bg-muted/30">
              {weekMarkers.map((m, i) => (
                <div
                  key={i}
                  className="absolute top-0 bottom-0 border-l border-border/50"
                  style={{ left: `${(m.offset / rangeDays) * 100}%` }}
                >
                  {m.isMonthStart && (
                    <span className="ml-1 text-[10px] text-muted-foreground">{m.label}</span>
                  )}
                </div>
              ))}
              {todayOffset >= 0 && todayOffset < rangeDays && (
                <div
                  className="absolute top-0 bottom-0 z-10 w-0.5 bg-primary"
                  style={{ left: `${(todayOffset / rangeDays) * 100}%` }}
                />
              )}
            </div>

            {visibleTreatments.map((t) => {
              const isOngoing = !t.end_date
              const start = toDate(t.start_date)
              const end = isOngoing ? rangeEnd : toDate(t.end_date as string)
              const barStart = Math.max(0, daysBetween(rangeStart, start))
              const barEnd = Math.min(rangeDays - 1, daysBetween(rangeStart, end))
              const leftPct = (barStart / rangeDays) * 100
              const widthPct = ((barEnd - barStart + 1) / rangeDays) * 100
              const barClass = TYPE_BAR_CLASSES[t.type] ?? TYPE_BAR_CLASSES.other
              const clippedLeft = start < rangeStart
              const clippedRight = !isOngoing && end > rangeEnd

              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => onTreatmentClick(t)}
                  className="relative flex h-10 w-full items-center border-b border-border/50 last:border-b-0 hover:bg-muted/30"
                >
                  {weekMarkers.map((m, i) => (
                    <div
                      key={i}
                      className="absolute top-0 bottom-0 border-l border-border/20"
                      style={{ left: `${(m.offset / rangeDays) * 100}%` }}
                    />
                  ))}
                  {todayOffset >= 0 && todayOffset < rangeDays && (
                    <div
                      className="absolute top-0 bottom-0 z-10 w-0.5 bg-primary/30"
                      style={{ left: `${(todayOffset / rangeDays) * 100}%` }}
                    />
                  )}
                  <div
                    className={cn(
                      'absolute top-2 bottom-2 rounded-full',
                      barClass,
                      clippedLeft && 'rounded-l-none',
                      (clippedRight || isOngoing) && 'rounded-r-none',
                      isOngoing && '[mask-image:linear-gradient(to_right,black_70%,transparent_98%)]',
                    )}
                    style={{ left: `${leftPct}%`, width: `${widthPct}%`, minWidth: '4px' }}
                  />
                  <span
                    className="absolute top-1/2 z-20 -translate-y-1/2 truncate px-1 text-[10px] font-medium text-white drop-shadow-sm"
                    style={{
                      left: `${leftPct}%`,
                      maxWidth: `${widthPct}%`,
                    }}
                  >
                    {t.name}
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

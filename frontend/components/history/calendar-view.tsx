'use client'

import { formatLocalDate } from '@/lib/utils'
import { getOverallTier, type ScaleTier } from '@/lib/checkin/scale-labels'
import type { Entry } from '@/lib/api/types'

interface CalendarViewProps {
  month: string // YYYY-MM
  entries: Entry[]
  onDayClick: (date: string) => void
}

function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate()
}

function getFirstDayOfWeek(year: number, month: number): number {
  // 0=Sunday, adjust to Monday-based (0=Monday)
  const day = new Date(year, month, 1).getDay()
  return day === 0 ? 6 : day - 1
}

const OVERALL_DOT_CLASS: Record<ScaleTier, string> = {
  good: 'bg-green-500',
  neutral: 'bg-amber-500',
  poor: 'bg-red-500',
}

const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

export function CalendarView({ month, entries, onDayClick }: CalendarViewProps) {
  const [yearStr, monthStr] = month.split('-')
  const year = parseInt(yearStr)
  const monthIdx = parseInt(monthStr) - 1
  const daysInMonth = getDaysInMonth(year, monthIdx)
  const firstDay = getFirstDayOfWeek(year, monthIdx)

  const entryMap = new Map<string, Entry>()
  entries.forEach((entry) => {
    entryMap.set(entry.date, entry)
  })

  const today = formatLocalDate(new Date())

  const cells: (number | null)[] = []
  for (let i = 0; i < firstDay; i++) {
    cells.push(null)
  }
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push(d)
  }

  return (
    <div>
      <div className="grid grid-cols-7 gap-1">
        {DAY_NAMES.map((name) => (
          <div key={name} className="py-2 text-center text-xs font-medium text-muted-foreground">
            {name}
          </div>
        ))}
        {cells.map((day, i) => {
          if (day === null) {
            return <div key={`empty-${i}`} />
          }
          const dateStr = `${yearStr}-${monthStr}-${String(day).padStart(2, '0')}`
          const entry = entryMap.get(dateStr)
          const isToday = dateStr === today

          return (
            <button
              key={dateStr}
              type="button"
              onClick={() => onDayClick(dateStr)}
              className={`flex min-h-[44px] flex-col items-center justify-center gap-1 rounded-lg transition-colors hover:bg-muted ${
                isToday ? 'ring-2 ring-primary' : ''
              }`}
            >
              <span className="text-sm">{day}</span>
              {entry && (
                <span className={`size-2 rounded-full ${OVERALL_DOT_CLASS[getOverallTier(entry.overall, entry.schema_version)]}`} />
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}

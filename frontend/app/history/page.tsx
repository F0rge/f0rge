'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react'
import { CalendarView } from '@/components/history/calendar-view'
import { EntryCard } from '@/components/history/entry-card'
import { useEntries } from '@/lib/api/hooks'

function getCurrentMonth(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function shiftMonth(month: string, delta: number): string {
  const [yearStr, monthStr] = month.split('-')
  let year = parseInt(yearStr)
  let m = parseInt(monthStr) + delta
  if (m < 1) {
    m = 12
    year--
  } else if (m > 12) {
    m = 1
    year++
  }
  return `${year}-${String(m).padStart(2, '0')}`
}

function formatMonthLabel(month: string): string {
  const [yearStr, monthStr] = month.split('-')
  const date = new Date(parseInt(yearStr), parseInt(monthStr) - 1)
  return date.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' })
}

export default function HistoryPage() {
  const router = useRouter()
  const [month, setMonth] = useState(getCurrentMonth)
  const { data: entries, isLoading } = useEntries(month)

  const sortedEntries = entries
    ? [...entries].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 7)
    : []

  return (
    <div className="mx-auto w-full max-w-lg p-4">
      <div className="mb-6">
        <h1 className="text-xl font-semibold tracking-tight">History</h1>
      </div>

      <div className="mb-4 flex items-center justify-between">
        <button
          type="button"
          onClick={() => setMonth((prev) => shiftMonth(prev, -1))}
          className="flex size-10 items-center justify-center rounded-lg transition-colors hover:bg-muted"
        >
          <ChevronLeft className="size-5" />
        </button>
        <span className="text-sm font-medium">{formatMonthLabel(month)}</span>
        <button
          type="button"
          onClick={() => setMonth((prev) => shiftMonth(prev, 1))}
          className="flex size-10 items-center justify-center rounded-lg transition-colors hover:bg-muted"
        >
          <ChevronRight className="size-5" />
        </button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <>
          <CalendarView
            month={month}
            entries={entries ?? []}
            onDayClick={(date) => router.push(`/history/${date}`)}
          />

          {sortedEntries.length > 0 && (
            <div className="mt-8">
              <h2 className="mb-3 text-sm font-medium text-muted-foreground">Recent entries</h2>
              <div className="space-y-2">
                {sortedEntries.map((entry) => (
                  <EntryCard
                    key={entry.id}
                    entry={entry}
                    onClick={() => router.push(`/history/${entry.date}`)}
                  />
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

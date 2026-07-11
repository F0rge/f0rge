'use client'

import { Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { ChevronLeft, ChevronRight, Loader2 } from 'lucide-react'
import { CalendarView } from '@/components/history/calendar-view'
import { EntryCard } from '@/components/history/entry-card'
import { ProtocolStreakHint } from '@/components/history/protocol-streak-hint'
import { PageShell } from '@/components/layout/page-shell'
import { PageHeader } from '@/components/layout/page-header'
import { FetchError } from '@/components/shared/fetch-error'
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

function HistoryContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const month = searchParams.get('month') ?? getCurrentMonth()
  const { data: entries, isLoading, isError, refetch } = useEntries(month)

  function setMonth(next: string) {
    const params = new URLSearchParams(searchParams.toString())
    params.set('month', next)
    router.replace(`/history?${params.toString()}`)
  }

  const sortedEntries = entries
    ? [...entries].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 7)
    : []

  return (
    <PageShell>
      <PageHeader title="History" />

      <div className="mb-4 flex items-center justify-between">
        <button
          type="button"
          onClick={() => setMonth(shiftMonth(month, -1))}
          className="flex size-10 items-center justify-center rounded-lg transition-colors hover:bg-muted"
        >
          <ChevronLeft className="size-5" />
        </button>
        <span className="text-sm font-medium">{formatMonthLabel(month)}</span>
        <button
          type="button"
          onClick={() => setMonth(shiftMonth(month, 1))}
          className="flex size-10 items-center justify-center rounded-lg transition-colors hover:bg-muted"
        >
          <ChevronRight className="size-5" />
        </button>
      </div>

      <ProtocolStreakHint month={month} />

      {isError ? (
        <FetchError message="Failed to load history." onRetry={() => refetch()} />
      ) : isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="grid grid-cols-12 gap-6">
          <div className="col-span-12 lg:col-span-7" data-tour="history-calendar">
            <CalendarView
              month={month}
              entries={entries ?? []}
              onDayClick={(date) => router.push(`/history/${date}`)}
            />
          </div>

          {sortedEntries.length > 0 && (
            <div className="col-span-12 lg:col-span-5">
              <h2 className="mb-3 text-sm font-medium text-muted-foreground">Recent entries</h2>
              <div className="space-y-2 lg:max-h-[calc(100vh-280px)] lg:overflow-y-auto">
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
        </div>
      )}
    </PageShell>
  )
}

export default function HistoryPage() {
  return (
    <Suspense>
      <HistoryContent />
    </Suspense>
  )
}

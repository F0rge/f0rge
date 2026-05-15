'use client'

import Link from 'next/link'
import { Loader2, Settings } from 'lucide-react'
import { CheckinForm } from '@/components/checkin/checkin-form'
import { useEntry } from '@/lib/api/hooks'

function getTodayDate() {
  const now = new Date()
  return now.toISOString().split('T')[0]
}

function formatDisplayDate(dateStr: string) {
  const date = new Date(dateStr + 'T00:00:00')
  return date.toLocaleDateString('en-GB', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

export default function CheckinPage() {
  const today = getTodayDate()
  const { data: entry, isLoading } = useEntry(today)

  return (
    <div className="mx-auto w-full max-w-lg p-4">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Check-in</h1>
          <p className="text-sm text-muted-foreground">{formatDisplayDate(today)}</p>
        </div>
        <Link
          href="/settings"
          className="flex items-center gap-1.5 rounded-lg px-2 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <Settings className="size-4" />
        </Link>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <CheckinForm
          date={today}
          existingEntry={entry ?? null}
        />
      )}
    </div>
  )
}

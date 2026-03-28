'use client'

import { use } from 'react'
import Link from 'next/link'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { CheckinForm } from '@/components/checkin/checkin-form'
import { useEntry } from '@/lib/api/hooks'

function formatDisplayDate(dateStr: string) {
  const date = new Date(dateStr + 'T00:00:00')
  return date.toLocaleDateString('en-GB', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  })
}

export default function CheckinDatePage({ params }: { params: Promise<{ date: string }> }) {
  const { date } = use(params)
  const { data: entry, isLoading } = useEntry(date)

  return (
    <div className="mx-auto w-full max-w-lg p-4">
      <div className="mb-6">
        <Link
          href="/history"
          className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Back
        </Link>
        <h1 className="text-xl font-semibold tracking-tight">Edit Entry</h1>
        <p className="text-sm text-muted-foreground">{formatDisplayDate(date)}</p>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <CheckinForm
          date={date}
          existingEntry={entry ?? null}
        />
      )}
    </div>
  )
}

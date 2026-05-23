'use client'

import { use, useState, useEffect, useRef, useCallback } from 'react'
import Link from 'next/link'
import { ArrowLeft, Loader2 } from 'lucide-react'
import { CheckinForm } from '@/components/checkin/checkin-form'
import { AutosaveStatusPill } from '@/components/checkin/autosave-status-pill'
import { useEntry } from '@/lib/api/hooks'
import type { AutosaveState } from '@/lib/hooks/use-autosave-entry'

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

  const [autosaveState, setAutosaveState] = useState<AutosaveState>({
    status: 'idle',
    lastSavedAt: null,
    errorMessage: null,
  })

  // Stable refs to autosave functions — registered once by the form, never cause re-renders.
  const flushRef = useRef<(() => void) | null>(null)
  const flushBeaconRef = useRef<(() => void) | null>(null)
  const retryRef = useRef<(() => void) | null>(null)

  const handleAutosaveStateChange = useCallback((state: AutosaveState) => {
    setAutosaveState(state)
  }, [])

  const handleAutosaveFnsReady = useCallback(
    (fns: { flush: () => void; forceFlush: () => Promise<void>; retry: () => void; flushBeacon: () => void }) => {
      flushRef.current = fns.flush
      flushBeaconRef.current = fns.flushBeacon
      retryRef.current = fns.retry
    },
    [],
  )

  // pagehide: use keepalive fetch / sendBeacon so the request survives tab close.
  useEffect(() => {
    const handlePageHide = () => {
      flushBeaconRef.current?.()
    }
    window.addEventListener('pagehide', handlePageHide)
    return () => window.removeEventListener('pagehide', handlePageHide)
  }, [])

  return (
    <div className="mx-auto w-full max-w-lg p-4">
      <div className="mb-6">
        <div className="mb-3 flex items-center justify-between">
          <Link
            href="/history"
            className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="size-4" />
            Back
          </Link>
          <AutosaveStatusPill
            status={autosaveState.status}
            lastSavedAt={autosaveState.lastSavedAt}
            errorMessage={autosaveState.errorMessage}
            onRetry={() => retryRef.current?.()}
          />
        </div>
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
          onAutosaveStateChange={handleAutosaveStateChange}
          onAutosaveFnsReady={handleAutosaveFnsReady}
        />
      )}
    </div>
  )
}

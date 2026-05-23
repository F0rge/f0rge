'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import Link from 'next/link'
import { Loader2, Settings } from 'lucide-react'
import { CheckinBoard } from '@/components/checkin/checkin-board'
import { AutosaveStatusPill } from '@/components/checkin/autosave-status-pill'
import { PhotoFocusOverlay } from '@/components/shared/food-analysis/photo-focus-overlay'
import { useEntry } from '@/lib/api/hooks'
import type { AutosaveState } from '@/lib/hooks/use-autosave-entry'

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

  const [autosaveState, setAutosaveState] = useState<AutosaveState>({
    status: 'idle',
    lastSavedAt: null,
    errorMessage: null,
  })

  // Stable refs to autosave functions — registered once by the form via onAutosaveFnsReady.
  // Stored as refs (not state) so updating them never triggers a re-render.
  const flushRef = useRef<(() => void) | null>(null)
  const flushBeaconRef = useRef<(() => void) | null>(null)
  const retryRef = useRef<(() => void) | null>(null)

  // Focus-mode overlay state. `null` = closed; a photo id = open and editing
  // that photo's ingredients in the comfortable full-width Dialog.
  // See issue #76 — PhotoFocusOverlay.
  const [focusedPhotoId, setFocusedPhotoId] = useState<number | null>(null)
  const handleClosePhotoFocus = useCallback(() => {
    setFocusedPhotoId(null)
    // Land any pending ingredient edits before the inline thumbnail re-renders.
    flushRef.current?.()
  }, [])

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
    <div className="mx-auto w-full max-w-7xl p-4 lg:px-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Check-in</h1>
          <p className="text-sm text-muted-foreground">{formatDisplayDate(today)}</p>
        </div>
        <div className="flex items-center gap-2">
          <AutosaveStatusPill
            status={autosaveState.status}
            lastSavedAt={autosaveState.lastSavedAt}
            errorMessage={autosaveState.errorMessage}
            onRetry={() => retryRef.current?.()}
          />
          <Link
            href="/settings"
            className="flex items-center gap-1.5 rounded-lg px-2 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <Settings className="size-4" />
          </Link>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <CheckinBoard
          date={today}
          existingEntry={entry ?? null}
          onAutosaveStateChange={handleAutosaveStateChange}
          onAutosaveFnsReady={handleAutosaveFnsReady}
          onOpenPhotoFocus={setFocusedPhotoId}
        />
      )}

      <PhotoFocusOverlay
        photoId={focusedPhotoId}
        photos={entry?.photos ?? []}
        onClose={handleClosePhotoFocus}
        onSelectPhoto={setFocusedPhotoId}
      />
    </div>
  )
}

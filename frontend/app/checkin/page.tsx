'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import Link from 'next/link'
import { Loader2, Settings, LayoutList } from 'lucide-react'
import { CheckinBoard } from '@/components/checkin/checkin-board'
import { AutosaveStatusPill } from '@/components/checkin/autosave-status-pill'
import { PhotoFocusOverlay } from '@/components/shared/food-analysis/photo-focus-overlay'
import { useEntry } from '@/lib/api/hooks'
import type { AutosaveState } from '@/lib/hooks/use-autosave-entry'
import { resetCardOrder } from '@/lib/checkin/card-order'

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
  const flushRef = useRef<(() => void) | null>(null)
  const flushBeaconRef = useRef<(() => void) | null>(null)
  const retryRef = useRef<(() => void) | null>(null)

  // Layout version — bumping remounts CheckinBoard so it re-reads card order from localStorage.
  const [layoutVersion, setLayoutVersion] = useState(0)

  // Reorder mode — toggled by the LayoutList button in the header.
  // When active, CheckinBoard shows the compact tile list instead of full cards.
  const [isReorderMode, setIsReorderMode] = useState(false)

  const handleCardOrderChange = useCallback(() => {
    // No-op: we no longer track hasCustomLayout separately.
    // The order is persisted in localStorage by CheckinBoard itself.
  }, [])

  const handleEnterReorderMode = useCallback(() => {
    setIsReorderMode(true)
  }, [])

  const handleExitReorderMode = useCallback(() => {
    setIsReorderMode(false)
    // Bump layout version so CheckinBoard remounts and re-reads the saved order.
    setLayoutVersion((v) => v + 1)
  }, [])

  // "Reset layout" is now surfaced as a button only inside reorder mode (in the future),
  // or via the existing resetCardOrder export. Keep the function available.
  const handleResetLayout = useCallback(() => {
    resetCardOrder()
    setIsReorderMode(false)
    setLayoutVersion((v) => v + 1)
  }, [])
  // Suppress unused-variable warning — will be wired to a tile in a future iteration.
  void handleResetLayout

  // Focus-mode overlay state. `null` = closed; a photo id = open and editing that photo.
  const [focusedPhotoId, setFocusedPhotoId] = useState<number | null>(null)
  const handleClosePhotoFocus = useCallback(() => {
    setFocusedPhotoId(null)
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
          {/* Autosave pill — hidden in reorder mode to reduce visual noise */}
          {!isReorderMode && (
            <AutosaveStatusPill
              status={autosaveState.status}
              lastSavedAt={autosaveState.lastSavedAt}
              errorMessage={autosaveState.errorMessage}
              onRetry={() => retryRef.current?.()}
            />
          )}

          {/* Reorder / Done toggle */}
          {isReorderMode ? (
            <button
              onClick={handleExitReorderMode}
              className="rounded-lg px-3 py-1.5 text-sm font-semibold text-primary transition-colors hover:bg-muted"
            >
              Done
            </button>
          ) : (
            <button
              onClick={handleEnterReorderMode}
              className="flex items-center gap-1.5 rounded-lg px-2 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              aria-label="Reorder cards"
              title="Reorder cards"
            >
              <LayoutList className="size-4" />
            </button>
          )}

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
          key={layoutVersion}
          date={today}
          existingEntry={entry ?? null}
          onAutosaveStateChange={handleAutosaveStateChange}
          onAutosaveFnsReady={handleAutosaveFnsReady}
          onOpenPhotoFocus={setFocusedPhotoId}
          onCardOrderChange={handleCardOrderChange}
          isReorderMode={isReorderMode}
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

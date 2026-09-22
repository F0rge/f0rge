'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { CheckinBoard } from '@/components/checkin/checkin-board'
import { CheckinBoardSkeleton } from '@/components/checkin/checkin-board-skeleton'
import { AutosaveStatusPill } from '@/components/checkin/autosave-status-pill'
import { FloatingStatusCapsule } from '@/components/checkin/floating-status-capsule'
import { CheckinPageHeader } from '@/components/checkin/checkin-page-header'
import { PageShell } from '@/components/layout/page-shell'
import { PhotoFocusOverlay } from '@/components/shared/food-analysis/photo-focus-overlay'
import { FetchError, formatLocalDate } from '@f0rge/ui'
import { useEntry } from '@/lib/api/hooks'
import type { AutosaveState } from '@/lib/hooks/use-autosave-entry'

export default function CheckinPage() {
  const [today, setToday] = useState(() => formatLocalDate(new Date()))
  const { data: entry, isLoading, isError, refetch } = useEntry(today)
  const headerRef = useRef<HTMLDivElement | null>(null)

  const [autosaveState, setAutosaveState] = useState<AutosaveState>({
    status: 'idle',
    lastSavedAt: null,
    errorMessage: null,
  })

  const flushRef = useRef<(() => void) | null>(null)
  const flushBeaconRef = useRef<(() => void) | null>(null)
  const retryRef = useRef<(() => void) | null>(null)

  const [focusedPhotoId, setFocusedPhotoId] = useState<number | null>(null)
  const handleClosePhotoFocus = useCallback(() => {
    setFocusedPhotoId(null)
    flushRef.current?.()
  }, [])

  const entryPhotos = entry?.photos ?? []
  const focusedPhoto =
    focusedPhotoId !== null && entryPhotos.some((p) => p.id === focusedPhotoId)
      ? focusedPhotoId
      : null

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

  useEffect(() => {
    const syncToday = () => {
      const next = formatLocalDate(new Date())
      setToday((prev) => (prev === next ? prev : next))
    }
    syncToday()
    const interval = window.setInterval(syncToday, 60_000)
    const onVisible = () => {
      if (document.visibilityState === 'visible') syncToday()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      window.clearInterval(interval)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [])

  useEffect(() => {
    const handlePageHide = () => {
      flushBeaconRef.current?.()
    }
    window.addEventListener('pagehide', handlePageHide)
    return () => window.removeEventListener('pagehide', handlePageHide)
  }, [])

  return (
    <>
      <FloatingStatusCapsule
        date={today}
        status={autosaveState.status}
        lastSavedAt={autosaveState.lastSavedAt}
        errorMessage={autosaveState.errorMessage}
        onRetry={() => retryRef.current?.()}
        sentinelRef={headerRef}
        hidden={isLoading}
      />
      <PageShell>
        <CheckinPageHeader
          date={today}
          headerRef={headerRef}
          actions={
            <AutosaveStatusPill
              status={autosaveState.status}
              lastSavedAt={autosaveState.lastSavedAt}
              errorMessage={autosaveState.errorMessage}
              onRetry={() => retryRef.current?.()}
            />
          }
        />

        {isError ? (
          <FetchError
            message="Failed to load today's check-in."
            onRetry={() => refetch()}
          />
        ) : isLoading ? (
          <CheckinBoardSkeleton />
        ) : (
          <CheckinBoard
            key={today}
            date={today}
            existingEntry={entry ?? null}
            onAutosaveStateChange={handleAutosaveStateChange}
            onAutosaveFnsReady={handleAutosaveFnsReady}
            onOpenPhotoFocus={setFocusedPhotoId}
          />
        )}

        <PhotoFocusOverlay
          photoId={focusedPhoto}
          photos={entryPhotos}
          onClose={handleClosePhotoFocus}
          onSelectPhoto={setFocusedPhotoId}
        />
      </PageShell>
    </>
  )
}

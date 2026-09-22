'use client'

import { use, useState, useEffect, useRef, useCallback } from 'react'
import { CheckinBoard } from '@/components/checkin/checkin-board'
import { CheckinBoardSkeleton } from '@/components/checkin/checkin-board-skeleton'
import { AutosaveStatusPill } from '@/components/checkin/autosave-status-pill'
import { FloatingStatusCapsule } from '@/components/checkin/floating-status-capsule'
import { CheckinPageHeader } from '@/components/checkin/checkin-page-header'
import { PageShell } from '@/components/layout/page-shell'
import { PhotoFocusOverlay } from '@/components/shared/food-analysis/photo-focus-overlay'
import { FetchError } from '@f0rge/ui'
import { useEntry } from '@/lib/api/hooks'
import type { AutosaveState } from '@/lib/hooks/use-autosave-entry'

export default function CheckinDatePage({ params }: { params: Promise<{ date: string }> }) {
  const { date } = use(params)
  const { data: entry, isLoading, isError, refetch } = useEntry(date)
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
    const handlePageHide = () => {
      flushBeaconRef.current?.()
    }
    window.addEventListener('pagehide', handlePageHide)
    return () => window.removeEventListener('pagehide', handlePageHide)
  }, [])

  return (
    <>
      <FloatingStatusCapsule
        date={date}
        status={autosaveState.status}
        lastSavedAt={autosaveState.lastSavedAt}
        errorMessage={autosaveState.errorMessage}
        onRetry={() => retryRef.current?.()}
        sentinelRef={headerRef}
        hidden={isLoading}
      />
      <PageShell>
        <CheckinPageHeader
          date={date}
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
            message="Failed to load this check-in."
            onRetry={() => refetch()}
          />
        ) : isLoading ? (
          <CheckinBoardSkeleton />
        ) : (
          <CheckinBoard
            key={date}
            date={date}
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

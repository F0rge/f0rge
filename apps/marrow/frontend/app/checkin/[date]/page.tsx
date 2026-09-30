'use client'

import { use, useState, useEffect, useRef, useCallback } from 'react'
import { toast } from 'sonner'
import { CheckinBoard } from '@/components/checkin/checkin-board'
import { CheckinBoardSkeleton } from '@/components/checkin/checkin-board-skeleton'
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
  const lastErrorToastKeyRef = useRef<string | null>(null)

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
    if (autosaveState.status !== 'error') {
      lastErrorToastKeyRef.current = null
      return
    }
    const key = autosaveState.errorMessage ?? 'save-error'
    if (lastErrorToastKeyRef.current === key) return
    lastErrorToastKeyRef.current = key
    toast.error(autosaveState.errorMessage ?? "Couldn't save your check-in.", {
      action: {
        label: 'Retry',
        onClick: () => retryRef.current?.(),
      },
    })
  }, [autosaveState.status, autosaveState.errorMessage])

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
        sentinelRef={headerRef}
        hidden={isLoading}
      />
      <PageShell>
        <CheckinPageHeader date={date} headerRef={headerRef} />

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

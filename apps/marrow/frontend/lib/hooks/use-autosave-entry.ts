'use client'

import { useRef, useState, useEffect, useCallback } from 'react'
import { useQueryClient, useMutation } from '@tanstack/react-query'
import { apiPost, apiPut, ApiError } from '@f0rge/ui/api'
import type { Entry, EntryCreate } from '@/lib/api/types'
import { invalidateSignals } from '@/lib/api/hooks/signals'

export type AutosaveStatus = 'idle' | 'saving' | 'saved' | 'error' | 'blocked'

export interface AutosaveState {
  status: AutosaveStatus
  lastSavedAt: number | null
  errorMessage: string | null
}

interface UseAutosaveEntryArgs {
  date: string
  payload: EntryCreate | null
  enabled: boolean
  blocked: boolean
  hasExistingEntry: boolean
}

type PayloadPatch = Partial<EntryCreate>

interface UseAutosaveEntryReturn extends AutosaveState {
  flush: (patch?: PayloadPatch) => void
  forceFlush: (patch?: PayloadPatch) => Promise<void>
  retry: () => void
  flushBeacon: (patch?: PayloadPatch) => void
}

const DEBOUNCE_MS = 500
const MAX_RETRY_ATTEMPTS = 5
const BACKOFF_BASE_MS = 1000

// Silent create — sets query data instead of invalidating, preventing hydration re-run.
// networkMode:'always' ensures mutateAsync rejects immediately when offline instead of
// suspending in React Query's pause queue (which would block our retry chain).
function useCreateEntrySilent(date: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: EntryCreate) => apiPost('/entries', data) as Promise<Entry>,
    networkMode: 'always',
    onSuccess: (serverEntry: Entry) => {
      queryClient.setQueryData(['entry', date], serverEntry)
      // Still refresh the list so history view updates.
      queryClient.invalidateQueries({ queryKey: ['entries'] })
      queryClient.invalidateQueries({ queryKey: ['weather'] })
      queryClient.invalidateQueries({ queryKey: ['enriched'] })
      invalidateSignals(queryClient)
    },
  })
}

// Silent update — same pattern as create.
function useUpdateEntrySilent(date: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: EntryCreate) => apiPut(`/entries/${date}`, data) as Promise<Entry>,
    networkMode: 'always',
    onSuccess: (serverEntry: Entry) => {
      queryClient.setQueryData(['entry', date], serverEntry)
      queryClient.invalidateQueries({ queryKey: ['entries'] })
      queryClient.invalidateQueries({ queryKey: ['weather'] })
      queryClient.invalidateQueries({ queryKey: ['enriched'] })
      invalidateSignals(queryClient)
    },
  })
}

export function useAutosaveEntry({
  date,
  payload,
  enabled,
  blocked,
  hasExistingEntry,
}: UseAutosaveEntryArgs): UseAutosaveEntryReturn {
  const createMutation = useCreateEntrySilent(date)
  const updateMutation = useUpdateEntrySilent(date)

  // Refs — do not trigger re-renders.
  const lastSerializedRef = useRef<string | null>(null)
  const pendingPayloadRef = useRef<EntryCreate | null>(null)
  const inFlightRef = useRef(false)
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const retryAttemptRef = useRef(0)
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Track whether entry has been created during this session (even if prop hasn't updated yet).
  const entryCreatedRef = useRef(hasExistingEntry)

  // React state — drives re-renders only when these change.
  const [status, setStatus] = useState<AutosaveStatus>('idle')
  const [lastSavedAt, setLastSavedAt] = useState<number | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // Keep ref in sync with prop so we pick up server-confirmed existence.
  useEffect(() => {
    if (hasExistingEntry) entryCreatedRef.current = true
  }, [hasExistingEntry])

  const clearDebounce = useCallback(() => {
    if (debounceTimerRef.current !== null) {
      clearTimeout(debounceTimerRef.current)
      debounceTimerRef.current = null
    }
  }, [])

  const clearRetry = useCallback(() => {
    if (retryTimerRef.current !== null) {
      clearTimeout(retryTimerRef.current)
      retryTimerRef.current = null
    }
  }, [])

  // fireRef allows the fire function to call itself recursively without
  // needing to be listed in its own useCallback dependency array.
  const fireRef = useRef<() => Promise<void>>(async () => { /* initialised below */ })

  const fire = useCallback(async () => {
    const toSend = pendingPayloadRef.current
    if (!toSend) return

    const serialized = JSON.stringify(toSend)
    inFlightRef.current = true
    setStatus('saving')

    try {
      // Use create (POST) if entry hasn't been created yet, PUT otherwise.
      if (!entryCreatedRef.current) {
        await createMutation.mutateAsync(toSend)
        entryCreatedRef.current = true
      } else {
        await updateMutation.mutateAsync(toSend)
      }

      lastSerializedRef.current = serialized
      retryAttemptRef.current = 0
      setStatus('saved')
      setLastSavedAt(Date.now())
      setErrorMessage(null)

      // If payload drifted during the in-flight request, fire again immediately.
      const currentSerialized = JSON.stringify(pendingPayloadRef.current)
      if (currentSerialized !== serialized) {
        inFlightRef.current = false
        void fireRef.current()
        return
      }
    } catch (err) {
      let msg = 'Unknown error'
      if (err instanceof ApiError) {
        if (err.status === 409) {
          // Entry already exists — flip to update mode and retry.
          entryCreatedRef.current = true
          inFlightRef.current = false
          void fireRef.current()
          return
        }
        msg = err.message
      } else if (err instanceof Error) {
        msg = err.message
      }

      retryAttemptRef.current += 1
      setErrorMessage(msg)

      if (retryAttemptRef.current >= MAX_RETRY_ATTEMPTS) {
        setStatus('error')
        inFlightRef.current = false
        return
      }

      // Exponential backoff: 1s, 2s, 4s, capped at 30s.
      const backoffMs = Math.min(
        BACKOFF_BASE_MS * Math.pow(2, retryAttemptRef.current - 1),
        30_000,
      )
      clearRetry()
      retryTimerRef.current = setTimeout(() => {
        inFlightRef.current = false
        void fireRef.current()
      }, backoffMs)
      return
    }

    inFlightRef.current = false
  }, [createMutation, updateMutation, clearRetry])

  // Keep the ref current so recursive calls always use the latest version.
  // Must be in a layout effect (not render) to satisfy react-hooks/refs.
  useEffect(() => {
    fireRef.current = fire
  })

  // React to payload/enabled changes.
  useEffect(() => {
    if (payload === null) {
      clearDebounce()
      return
    }

    const serialized = JSON.stringify(payload)
    if (serialized === lastSerializedRef.current) return

    // Not dirty yet: hydration / check-in defaults are settling into form state.
    // Stage the payload so forceFlush (photo-first) can still create a row, but
    // also baseline lastSerializedRef so flush()/flushBeacon() (pagehide) do
    // not persist an empty-day visit just because defaults prefilled the form.
    // Once `enabled` flips true (a real edit), staging resumes for autosave.
    if (!enabled) {
      pendingPayloadRef.current = payload
      lastSerializedRef.current = serialized
      clearDebounce()
      return
    }

    // Stage the payload and debounce-save when dirty.
    pendingPayloadRef.current = payload
    clearDebounce()

    // setStatus is called inside the timer callback (not synchronously in the
    // effect body) to satisfy react-hooks/set-state-in-effect.
    debounceTimerRef.current = setTimeout(() => {
      setStatus('saving')
      if (!inFlightRef.current) {
        void fireRef.current()
      }
    }, DEBOUNCE_MS)
  }, [payload, enabled, clearDebounce])

  // Cleanup on unmount.
  useEffect(() => {
    return () => {
      clearDebounce()
      clearRetry()
    }
  }, [clearDebounce, clearRetry])

  const applyPayloadPatch = useCallback((patch?: PayloadPatch) => {
    if (!patch || !pendingPayloadRef.current) return
    pendingPayloadRef.current = { ...pendingPayloadRef.current, ...patch }
  }, [])

  // flush: clear debounce and fire now if there's something pending.
  const flush = useCallback((patch?: PayloadPatch) => {
    applyPayloadPatch(patch)
    clearDebounce()
    if (pendingPayloadRef.current && !inFlightRef.current) {
      const serialized = JSON.stringify(pendingPayloadRef.current)
      if (serialized !== lastSerializedRef.current) {
        void fire()
      }
    }
  }, [applyPayloadPatch, clearDebounce, fire])

  // forceFlush: fires even if payload matches last sent — used by photo upload to ensure
  // an entry row exists before uploading a photo.
  const forceFlush = useCallback(async (patch?: PayloadPatch) => {
    applyPayloadPatch(patch)
    clearDebounce()
    if (pendingPayloadRef.current && !inFlightRef.current) {
      await fire()
    }
  }, [applyPayloadPatch, clearDebounce, fire])

  const retry = useCallback(() => {
    clearRetry()
    retryAttemptRef.current = 0
    inFlightRef.current = false
    void fire()
  }, [clearRetry, fire])

  // flushBeacon: safe to call during pagehide — uses keepalive fetch (PUT) or
  // sendBeacon (POST) so the request survives page teardown. No-ops when
  // pendingPayload matches the last successfully serialized value.
  const flushBeacon = useCallback((patch?: PayloadPatch) => {
    applyPayloadPatch(patch)
    const toSend = pendingPayloadRef.current
    if (!toSend) return

    const serialized = JSON.stringify(toSend)
    if (serialized === lastSerializedRef.current) return

    if (entryCreatedRef.current) {
      // Entry exists — use keepalive PUT (browser keeps socket open after page teardown).
      fetch(`/api/v1/entries/${date}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        keepalive: true,
        body: serialized,
      })
    } else {
      // Entry doesn't exist yet — sendBeacon is POST-only, which matches our create endpoint.
      navigator.sendBeacon(
        '/api/v1/entries',
        new Blob([serialized], { type: 'application/json' }),
      )
    }
  }, [applyPayloadPatch, date])

  // Derive blocked state at render time. `blocked` is a first-class prop (the
  // Bristol-gate flag) — not inferred from `enabled` — so clean page load
  // (enabled=false, blocked=false) correctly yields `status` ('idle'), not 'blocked'.
  const computedStatus: AutosaveStatus = blocked ? 'blocked' : status

  return { status: computedStatus, lastSavedAt, errorMessage, flush, forceFlush, retry, flushBeacon }
}

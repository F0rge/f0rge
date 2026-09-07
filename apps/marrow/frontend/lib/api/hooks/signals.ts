'use client'

import { useEffect, useState } from 'react'
import { keepPreviousData, useQuery, type QueryClient } from '@tanstack/react-query'
import { apiGet } from '@f0rge/ui/api'
import type { SignalsDriverJson, SignalsResponse } from '../types/signals'

const COMPUTING_POLL_MS = 1500
const COMPUTING_TIMEOUT_MS = 60_000

function normalizeSignals(body: Omit<SignalsResponse, 'drivers'> & { drivers: SignalsDriverJson[] }): SignalsResponse {
  return {
    ...body,
    drivers: body.drivers.map(({ class: feature_class, ...rest }) => ({
      ...rest,
      feature_class,
    })),
  }
}

export function useSignals(outcome: string, start: string, end: string) {
  const params = new URLSearchParams({ outcome, start, end })
  const scopeKey = `${outcome}|${start}|${end}`
  const [timeoutState, setTimeoutState] = useState({ scopeKey, timedOut: false })
  // Reset timeout when query params change (render-time adjust — no setState-in-effect).
  if (timeoutState.scopeKey !== scopeKey) {
    setTimeoutState({ scopeKey, timedOut: false })
  }
  const computingTimedOut = timeoutState.timedOut

  const query = useQuery<SignalsResponse>({
    queryKey: ['signals', outcome, start, end],
    queryFn: async () => {
      const raw = (await apiGet(
        `/signals?${params.toString()}`,
      )) as Omit<SignalsResponse, 'drivers'> & { drivers: SignalsDriverJson[] }
      return normalizeSignals(raw)
    },
    enabled: !!outcome && !!start && !!end,
    placeholderData: keepPreviousData,
    refetchInterval: (q) => {
      const data = q.state.data
      const computing = data?.meta?.computing === true
      const err = data?.meta?.compute_error
      return computing && !err && !computingTimedOut ? COMPUTING_POLL_MS : false
    },
  })

  const computing = query.data?.meta?.computing === true
  const computeError = query.data?.meta?.compute_error ?? null

  useEffect(() => {
    if (!computing || computeError) return
    const started = Date.now()
    const id = window.setInterval(() => {
      if (Date.now() - started >= COMPUTING_TIMEOUT_MS) {
        setTimeoutState({ scopeKey, timedOut: true })
      }
    }, 1000)
    return () => window.clearInterval(id)
  }, [computing, computeError, scopeKey])

  function refetchAndReset() {
    setTimeoutState({ scopeKey, timedOut: false })
    return query.refetch()
  }

  return {
    ...query,
    refetch: refetchAndReset,
    computing,
    computeError,
    computingTimedOut: computingTimedOut && computing && !computeError,
  }
}

export function invalidateSignals(queryClient: QueryClient) {
  return queryClient.invalidateQueries({ queryKey: ['signals'] })
}

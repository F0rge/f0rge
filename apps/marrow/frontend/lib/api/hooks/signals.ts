'use client'

import { useQuery } from '@tanstack/react-query'
import { apiGet } from '@f0rge/ui/api'
import type { SignalsDriverJson, SignalsResponse } from '../types/signals'

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
  return useQuery<SignalsResponse>({
    queryKey: ['signals', outcome, start, end],
    queryFn: async () => {
      const raw = (await apiGet(
        `/signals?${params.toString()}`,
      )) as Omit<SignalsResponse, 'drivers'> & { drivers: SignalsDriverJson[] }
      return normalizeSignals(raw)
    },
    enabled: !!outcome && !!start && !!end,
  })
}

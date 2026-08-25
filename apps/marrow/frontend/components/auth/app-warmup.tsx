'use client'

import { useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { apiGet, ApiError } from '@f0rge/ui/api'
import { formatLocalDate } from '@f0rge/ui'

export function AppWarmup() {
  const queryClient = useQueryClient()
  const warmed = useRef(false)

  useEffect(() => {
    if (warmed.current) return
    warmed.current = true

    const today = formatLocalDate(new Date())

    void Promise.all([
      queryClient.prefetchQuery({
        queryKey: ['supplement-catalog', false],
        queryFn: () => apiGet('/supplements/catalog'),
        staleTime: Infinity,
      }),
      queryClient.prefetchQuery({
        queryKey: ['medication-catalog', false],
        queryFn: () => apiGet('/medications/catalog'),
        staleTime: Infinity,
      }),
      queryClient.prefetchQuery({
        queryKey: ['medication-catalog', true],
        queryFn: () => apiGet('/medications/catalog?include_archived=true'),
        staleTime: Infinity,
      }),
      queryClient.prefetchQuery({
        queryKey: ['diet-tag-catalog', false],
        queryFn: () => apiGet('/diet-tags/catalog'),
        staleTime: Infinity,
      }),
      queryClient.prefetchQuery({
        queryKey: ['symptom-catalog', false],
        queryFn: () => apiGet('/symptoms/catalog'),
        staleTime: Infinity,
      }),
      queryClient.prefetchQuery({
        queryKey: ['trackers', false],
        queryFn: () => apiGet('/trackers'),
        staleTime: Infinity,
      }),
      queryClient.prefetchQuery({
        queryKey: ['entry', today],
        queryFn: async () => {
          try {
            return await apiGet(`/entries/${today}`)
          } catch (err) {
            if (err instanceof ApiError && err.status === 404) {
              return null
            }
            throw err
          }
        },
      }),
    ])
  }, [queryClient])

  return null
}

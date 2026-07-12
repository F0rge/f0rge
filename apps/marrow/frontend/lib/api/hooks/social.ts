'use client'

import { useQuery } from '@tanstack/react-query'
import { apiGet } from '@f0rge/ui/api'
import type { HandleAvailableResponse, PublicUserCard } from '../types/social'

export function useHandleAvailable(handle: string) {
  const normalized = handle.trim().toLowerCase().replace(/^@/, '')
  const enabled = normalized.length >= 3

  return useQuery<HandleAvailableResponse>({
    queryKey: ['social', 'handle-available', normalized],
    queryFn: () => apiGet(`/social/handle-available?handle=${encodeURIComponent(normalized)}`),
    enabled,
    staleTime: 30_000,
  })
}

export function useUserLookup(handle: string) {
  const normalized = handle.trim().toLowerCase().replace(/^@/, '')
  const enabled = normalized.length >= 3

  return useQuery<PublicUserCard>({
    queryKey: ['social', 'lookup', normalized],
    queryFn: () => apiGet(`/social/users/lookup?handle=${encodeURIComponent(normalized)}`),
    enabled,
    retry: false,
  })
}

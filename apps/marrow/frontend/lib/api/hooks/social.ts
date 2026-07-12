'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiDelete, apiGet, apiPost } from '@f0rge/ui/api'
import type { ConnectionListResponse, HandleAvailableResponse, PublicUserCard } from '../types/social'

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

export function useConnections() {
  return useQuery<ConnectionListResponse>({
    queryKey: ['social', 'connections'],
    queryFn: () => apiGet('/social/connections'),
  })
}

export function useSendConnectionRequest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (handle: string) => apiPost('/social/connections', { handle }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['social', 'connections'] })
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
    },
  })
}

export function useAcceptConnection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiPost(`/social/connections/${id}/accept`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['social', 'connections'] })
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
    },
  })
}

export function useDeleteConnection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiDelete(`/social/connections/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['social', 'connections'] })
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
    },
  })
}

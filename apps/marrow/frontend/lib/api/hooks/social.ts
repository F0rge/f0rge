'use client'

import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'
import { apiDelete, apiGet, apiPatch, apiPost } from '@f0rge/ui/api'
import type {
  ConnectionListResponse,
  GroupDetail,
  GroupListItem,
  HandleAvailableResponse,
  MealTagsResponse,
  PublicUserCard,
} from '../types/social'

function invalidateGroups(queryClient: QueryClient, groupId?: string) {
  queryClient.invalidateQueries({ queryKey: ['social', 'groups'] })
  if (groupId) {
    queryClient.invalidateQueries({ queryKey: ['social', 'groups', groupId] })
  }
  queryClient.invalidateQueries({ queryKey: ['notifications', 'unread'] })
}

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

function invalidateMealTags(queryClient: QueryClient) {
  queryClient.invalidateQueries({ queryKey: ['social', 'meal-tags'] })
  queryClient.invalidateQueries({ queryKey: ['entry'] })
  queryClient.invalidateQueries({ queryKey: ['entries'] })
  queryClient.invalidateQueries({ queryKey: ['notifications'] })
}

export function useMealTags() {
  return useQuery<MealTagsResponse>({
    queryKey: ['social', 'meal-tags'],
    queryFn: () => apiGet('/social/meal-tags'),
  })
}

export function useApproveMealTag() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiPost(`/social/meal-tags/${id}/approve`, {}),
    onSuccess: () => invalidateMealTags(queryClient),
  })
}

export function useDeclineMealTag() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiPost(`/social/meal-tags/${id}/decline`, {}),
    onSuccess: () => invalidateMealTags(queryClient),
  })
}

export function useCancelMealTag() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiDelete(`/social/meal-tags/${id}`),
    onSuccess: () => invalidateMealTags(queryClient),
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

export function useGroups() {
  return useQuery<GroupListItem[]>({
    queryKey: ['social', 'groups'],
    queryFn: () => apiGet('/social/groups'),
  })
}

export function useGroup(id: string) {
  return useQuery<GroupDetail>({
    queryKey: ['social', 'groups', id],
    queryFn: () => apiGet(`/social/groups/${id}`),
    enabled: Boolean(id),
  })
}

export function useCreateGroup() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => apiPost('/social/groups', { name }),
    onSuccess: () => invalidateGroups(queryClient),
  })
}

export function useRenameGroup() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      apiPatch(`/social/groups/${id}`, { name }),
    onSuccess: (_data, { id }) => invalidateGroups(queryClient, id),
  })
}

export function useDeleteGroup() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiDelete(`/social/groups/${id}`),
    onSuccess: (_data, id) => invalidateGroups(queryClient, id),
  })
}

export function useInviteToGroup() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, handle }: { id: string; handle: string }) =>
      apiPost(`/social/groups/${id}/invite`, { handle }),
    onSuccess: (_data, { id }) => invalidateGroups(queryClient, id),
  })
}

export function useAcceptGroupInvite() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => apiPost(`/social/groups/${id}/accept`, {}),
    onSuccess: (_data, id) => invalidateGroups(queryClient, id),
  })
}

export function useRemoveGroupMember() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, handle }: { id: string; handle: string }) =>
      apiDelete(`/social/groups/${id}/members/${encodeURIComponent(handle)}`),
    onSuccess: (_data, { id }) => invalidateGroups(queryClient, id),
  })
}

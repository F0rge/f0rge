'use client'

import { useEffect, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { apiGet, apiPost } from '@f0rge/ui/api'
import type { NotificationItem, UnreadCountResponse } from '../types/notifications'

export function useUnreadCount() {
  const previous = useRef<number | null>(null)

  const query = useQuery<UnreadCountResponse>({
    queryKey: ['notifications', 'unread'],
    queryFn: () => apiGet('/notifications/unread-count'),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
    staleTime: 0,
  })

  useEffect(() => {
    const count = query.data?.count
    if (count === undefined) return
    if (previous.current !== null && count > previous.current) {
      toast('New activity in People')
    }
    previous.current = count
  }, [query.data?.count])

  return query
}

export function useNotifications(limit = 30) {
  return useQuery<NotificationItem[]>({
    queryKey: ['notifications', 'list', limit],
    queryFn: () => apiGet(`/notifications?limit=${limit}`),
  })
}

export function useMarkRead() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: { ids?: string[]; all?: boolean }) =>
      apiPost('/notifications/read', body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
    },
  })
}

export function notificationCopy(item: NotificationItem): string {
  const p = item.payload
  switch (item.type) {
    case 'connection_request':
      return `@${p.handle ?? 'someone'} sent you a connection request`
    case 'connection_accepted':
      return `@${p.handle ?? 'someone'} accepted your connection request`
    case 'group_invite':
      return `@${p.handle ?? 'someone'} invited you to ${p.group_name ?? 'a group'}`
    case 'group_invite_accepted':
      return `@${p.handle ?? 'someone'} joined ${p.group_name ?? 'your group'}`
    case 'meal_tag_request':
      return `@${p.handle ?? 'someone'} tagged you on a meal — approval needed`
    case 'meal_tag_delivered':
      return `@${p.handle ?? 'someone'} shared a meal with you`
    default:
      return 'New activity'
  }
}

'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPut, apiPatch } from '@f0rge/ui/api'
import type { Tracker, TrackerValue, TrackerCreate, TrackerUpdate } from '../types'

export function useTrackers(includeArchived = false) {
  const params = includeArchived ? '?include_archived=true' : ''
  return useQuery<Tracker[]>({
    queryKey: ['trackers', includeArchived],
    queryFn: () => apiGet(`/trackers${params}`),
    staleTime: Infinity,
  })
}

export function useCreateTracker() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: TrackerCreate) => apiPost('/trackers', data) as Promise<Tracker>,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trackers'] })
    },
  })
}

export function useUpdateTracker() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: TrackerUpdate }) =>
      apiPatch(`/trackers/${id}`, data) as Promise<Tracker>,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trackers'] })
    },
  })
}

export function useReorderTrackers() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (order: number[]) => apiPatch('/trackers/reorder', { order }),
    onMutate: async (order: number[]) => {
      // Optimistically reorder customs so the dragged row settles in its new slot
      // immediately, instead of snapping back during the PATCH round-trip.
      await queryClient.cancelQueries({ queryKey: ['trackers'] })
      const snapshots: { key: readonly unknown[]; data: Tracker[] | undefined }[] = []
      const queries = queryClient.getQueriesData<Tracker[]>({ queryKey: ['trackers'] })
      for (const [key, data] of queries) {
        snapshots.push({ key, data })
        if (!data) continue
        const byId = new Map(data.map((t) => [t.id, t]))
        const reordered = order
          .map((id) => byId.get(id))
          .filter((t): t is Tracker => t !== undefined)
        const remaining = data.filter((t) => !order.includes(t.id))
        queryClient.setQueryData<Tracker[]>(key, [...remaining, ...reordered])
      }
      return { snapshots }
    },
    onError: (_err, _order, context) => {
      context?.snapshots.forEach(({ key, data }) => queryClient.setQueryData(key, data))
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['trackers'] }),
  })
}

export function useEntryTrackerValues(date: string) {
  return useQuery<TrackerValue[]>({
    queryKey: ['tracker-values', date],
    queryFn: () => apiGet(`/entries/${date}/tracker_values`),
    enabled: !!date,
  })
}

export function useUpsertTrackerValue(date: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ trackerId, value }: { trackerId: number; value: number }) =>
      apiPut(`/entries/${date}/tracker_values/${trackerId}`, { value }) as Promise<TrackerValue>,
    onMutate: async ({ trackerId, value }) => {
      // Optimistic update
      await queryClient.cancelQueries({ queryKey: ['tracker-values', date] })
      const prev = queryClient.getQueryData<TrackerValue[]>(['tracker-values', date])
      queryClient.setQueryData<TrackerValue[]>(['tracker-values', date], (old = []) => {
        const exists = old.find((tv) => tv.tracker_id === trackerId)
        if (exists) {
          return old.map((tv) =>
            tv.tracker_id === trackerId ? { ...tv, value } : tv,
          )
        }
        return [
          ...old,
          { tracker_id: trackerId, date, value, updated_at: new Date().toISOString() },
        ]
      })
      return { prev }
    },
    onError: (_err, _vars, context) => {
      if (context?.prev !== undefined) {
        queryClient.setQueryData(['tracker-values', date], context.prev)
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['tracker-values', date] })
    },
  })
}

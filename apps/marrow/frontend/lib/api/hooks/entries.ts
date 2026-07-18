'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  apiGet,
  apiPost,
  apiPut,
  apiPatch,
  apiDelete,
  handleMutationError,
  ApiError,
} from '@f0rge/ui/api'
import type { Entry, EntryCreate, EntryStats } from '../types'

export function useEntryStats() {
  return useQuery<EntryStats>({
    queryKey: ['entries', 'stats'],
    queryFn: () => apiGet('/entries/stats'),
  })
}

export function useEntries(month?: string) {
  const params = month ? `?month=${month}` : ''
  return useQuery<Entry[]>({
    queryKey: ['entries', month ?? 'all'],
    queryFn: () => apiGet(`/entries${params}`),
  })
}

export function useEntry(date: string) {
  return useQuery<Entry | null>({
    queryKey: ['entry', date],
    queryFn: async () => {
      try {
        return await apiGet(`/entries/${date}`)
      } catch (err) {
        // No entry yet for this date — render an empty check-in board.
        if (err instanceof ApiError && err.status === 404) {
          return null
        }
        throw err
      }
    },
    enabled: !!date,
    retry: false,
  })
}

export function useCreateEntry() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: EntryCreate) => apiPost('/entries', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entries'] })
      queryClient.invalidateQueries({ queryKey: ['entry'] })
    },
  })
}

export function useUpdateEntry() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ date, data }: { date: string; data: EntryCreate }) =>
      apiPut(`/entries/${date}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entries'] })
      queryClient.invalidateQueries({ queryKey: ['entry'] })
    },
  })
}

export function useDeleteEntry() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (date: string) => apiDelete(`/entries/${date}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entries'] })
      queryClient.invalidateQueries({ queryKey: ['entry'] })
    },
  })
}

export function useUpdatePhotoMealTime() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ photoId, mealTime }: { photoId: number; mealTime: string }) =>
      apiPatch(`/photos/${photoId}`, { meal_time: mealTime }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entry'] })
      queryClient.invalidateQueries({ queryKey: ['entries'] })
      queryClient.invalidateQueries({ queryKey: ['photos'] })
    },
  })
}

export function useUpdatePhotoLabel() {
  const queryClient = useQueryClient()
  return useMutation({
    // Empty string clears the label — server stores NULL.
    mutationFn: ({ photoId, label }: { photoId: number; label: string }) =>
      apiPatch(`/photos/${photoId}`, { label }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entry'] })
      queryClient.invalidateQueries({ queryKey: ['entries'] })
      queryClient.invalidateQueries({ queryKey: ['photo-analysis'] })
      queryClient.invalidateQueries({ queryKey: ['photos'] })
    },
  })
}

export function useUpdatePhotoVisibility() {
  const queryClient = useQueryClient()
  return useMutation({
    // hidden=true stamps hidden_at; false clears it. Hidden photos stay
    // visible in check-in — only the profile feed filters them.
    mutationFn: ({ photoId, hidden }: { photoId: number; hidden: boolean }) =>
      apiPatch(`/photos/${photoId}`, { hidden }),
    // No photo-analysis invalidation: the analysis payload carries neither
    // hidden_at nor diet tags.
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entry'] })
      queryClient.invalidateQueries({ queryKey: ['entries'] })
      queryClient.invalidateQueries({ queryKey: ['photos'] })
    },
  })
}

export function useUpdatePhotoDietTags() {
  const queryClient = useQueryClient()
  return useMutation({
    // Full replacement of the photo's explicit diet-tag set.
    mutationFn: ({ photoId, dietTags }: { photoId: number; dietTags: string[] }) =>
      apiPatch(`/photos/${photoId}`, { diet_tags: dietTags }),
    // No photo-analysis invalidation: explicit tags live outside the analysis.
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entry'] })
      queryClient.invalidateQueries({ queryKey: ['entries'] })
      queryClient.invalidateQueries({ queryKey: ['photos'] })
    },
  })
}

export function useUpdateDietaryConfirm() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      photoId,
      ...body
    }: {
      photoId: number
      gluten_free_confirmed?: boolean
      lactose_free_confirmed?: boolean
    }) => apiPut(`/photos/${photoId}/analysis/dietary-confirm`, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entry'] })
      queryClient.invalidateQueries({ queryKey: ['entries'] })
      queryClient.invalidateQueries({ queryKey: ['photo-analysis'] })
      // The recent-meals "Log again" strip carries backend-computed diet_flags
      // that also honour the confirmation gate — refresh it so it doesn't show
      // a stale Gluten/lactose flag next to the freshly confirmed-free meal.
      queryClient.invalidateQueries({ queryKey: ['meals', 'recent'] })
    },
    onError: (err) => handleMutationError(err, 'Failed to update dietary confirmation'),
  })
}

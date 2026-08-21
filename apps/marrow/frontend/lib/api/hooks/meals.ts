'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost } from '@f0rge/ui/api'
import type { Entry, Photo, PlatformMeal, RecentMeal } from '../types'
import { invalidateSignals } from './signals'

function mergePhotoIntoEntry(queryClient: ReturnType<typeof useQueryClient>, date: string, photo: Photo) {
  queryClient.setQueryData<Entry>(['entry', date], (old) => {
    if (!old) return old
    if (old.photos.some((p) => p.id === photo.id)) return old
    return { ...old, photos: [...old.photos, photo] }
  })
  queryClient.invalidateQueries({ queryKey: ['entry', date] })
  queryClient.invalidateQueries({ queryKey: ['entries'] })
  queryClient.invalidateQueries({ queryKey: ['meals', 'recent'] })
  invalidateSignals(queryClient)
}

export function useRecentMeals(limit = 12) {
  return useQuery<RecentMeal[]>({
    queryKey: ['meals', 'recent', limit],
    queryFn: () => apiGet(`/meals/recent?limit=${limit}`),
  })
}

export function useCloneMeal() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ date, sourcePhotoId }: { date: string; sourcePhotoId: number }) =>
      (await apiPost(`/entries/${date}/meals/clone`, {
        source_photo_id: sourcePhotoId,
      })) as Photo,
    onSuccess: (photo, { date }) => {
      mergePhotoIntoEntry(queryClient, date, photo)
    },
  })
}

export function usePlatformMeals({
  q,
  enabled = true,
}: { q?: string; enabled?: boolean } = {}) {
  const params = new URLSearchParams()
  if (q) params.set('q', q)
  const qs = params.toString()

  return useQuery<PlatformMeal[]>({
    queryKey: ['meals', 'library', q ?? ''],
    queryFn: () => apiGet(`/meals/library${qs ? `?${qs}` : ''}`),
    enabled,
    // Re-fetch when the sheet re-opens so a prior 5xx/empty cache cannot stick.
    refetchOnMount: 'always',
    retry: 1,
  })
}

export function useLogFromLibrary() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      date,
      platformMealId,
      mealTime,
    }: {
      date: string
      platformMealId: number
      mealTime?: string
    }) =>
      (await apiPost(`/entries/${date}/meals/from-library`, {
        platform_meal_id: platformMealId,
        ...(mealTime ? { meal_time: mealTime } : {}),
      })) as Photo,
    onSuccess: (photo, { date }) => {
      mergePhotoIntoEntry(queryClient, date, photo)
    },
  })
}

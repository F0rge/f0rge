'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost } from '@f0rge/ui/api'
import type { Entry, Photo, RecentMeal } from '../types'

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
      // Merge immediately so the food grid updates with the toast — do not wait
      // on a refetch that can still hit a stale Redis entry (or race autosave).
      queryClient.setQueryData<Entry>(['entry', date], (old) => {
        if (!old) return old
        if (old.photos.some((p) => p.id === photo.id)) return old
        return { ...old, photos: [...old.photos, photo] }
      })
      queryClient.invalidateQueries({ queryKey: ['entry', date] })
      queryClient.invalidateQueries({ queryKey: ['entries'] })
      queryClient.invalidateQueries({ queryKey: ['meals', 'recent'] })
    },
  })
}

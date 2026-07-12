'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost } from '@f0rge/ui/api'
import type { RecentMeal } from '../types'

export function useRecentMeals(limit = 12) {
  return useQuery<RecentMeal[]>({
    queryKey: ['meals', 'recent', limit],
    queryFn: () => apiGet(`/meals/recent?limit=${limit}`),
  })
}

export function useCloneMeal() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ date, sourcePhotoId }: { date: string; sourcePhotoId: number }) =>
      apiPost(`/entries/${date}/meals/clone`, { source_photo_id: sourcePhotoId }),
    onSuccess: (_data, { date }) => {
      // The cloned photo rides inside the entry response (Entry.photos), so
      // invalidating the day entry re-renders the food card with it; the month
      // list and the recent-meals list both shift too.
      queryClient.invalidateQueries({ queryKey: ['entry', date] })
      queryClient.invalidateQueries({ queryKey: ['entries'] })
      queryClient.invalidateQueries({ queryKey: ['meals', 'recent'] })
    },
  })
}

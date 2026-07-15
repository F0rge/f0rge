'use client'

import { useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPut, apiDelete, apiPostForm, ApiError } from '@f0rge/ui/api'
import type { Photo, PhotoAnalysis } from '../types'

export interface PhotoMealTagItem {
  id: string
  user: {
    handle: string
    display_name: string | null
    avatar_default_index: number
    has_custom_avatar: boolean
  }
  status: string
}

export interface PhotoMealTagListResponse {
  tags: PhotoMealTagItem[]
}

export function usePhotos(scope: 'all' | 'tagged', limit = 24) {
  return useQuery<Photo[]>({
    queryKey: ['photos', scope, limit],
    queryFn: () => apiGet(`/photos?scope=${scope}&limit=${limit}`),
  })
}

export function usePhotoTags(photoId: number, enabled = true) {
  return useQuery<PhotoMealTagListResponse>({
    queryKey: ['photo-tags', photoId],
    queryFn: () => apiGet(`/photos/${photoId}/tags`),
    enabled: enabled && photoId > 0,
  })
}

export function useAddPhotoTags() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      photoId,
      handles,
      groupIds = [],
    }: {
      photoId: number
      handles: string[]
      groupIds?: string[]
    }) => apiPost(`/photos/${photoId}/tags`, { handles, group_ids: groupIds }),
    onSuccess: (_data, { photoId }) => {
      queryClient.invalidateQueries({ queryKey: ['photo-tags', photoId] })
      queryClient.invalidateQueries({ queryKey: ['entry'] })
      queryClient.invalidateQueries({ queryKey: ['entries'] })
      queryClient.invalidateQueries({ queryKey: ['social', 'meal-tags'] })
      queryClient.invalidateQueries({ queryKey: ['notifications'] })
    },
  })
}

export function useUploadPhoto() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      date,
      file,
      label,
      mealTime,
      taggedHandles,
      taggedGroupIds,
    }: {
      date: string
      file: File
      label?: string
      mealTime?: Date | null
      taggedHandles?: string[]
      taggedGroupIds?: string[]
    }) => {
      const formData = new FormData()
      formData.append('file', file)
      if (label) formData.append('label', label)
      if (mealTime) formData.append('meal_time', mealTime.toISOString())
      if (taggedHandles && taggedHandles.length > 0) {
        formData.append('tagged_handles', JSON.stringify(taggedHandles))
      }
      if (taggedGroupIds && taggedGroupIds.length > 0) {
        formData.append('tagged_group_ids', JSON.stringify(taggedGroupIds))
      }
      return apiPostForm(`/entries/${date}/photos`, formData)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entry'] })
      queryClient.invalidateQueries({ queryKey: ['entries'] })
      queryClient.invalidateQueries({ queryKey: ['photos'] })
    },
  })
}

export function useDeletePhoto() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => apiDelete(`/photos/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entry'] })
      queryClient.invalidateQueries({ queryKey: ['entries'] })
      queryClient.invalidateQueries({ queryKey: ['photos'] })
    },
  })
}

export function usePhotoAnalysis(
  photoId: number | null,
  options?: { sharedMeal?: boolean },
) {
  const sharedMeal = options?.sharedMeal ?? false
  const queryClient = useQueryClient()
  const prevStatusRef = useRef<string | undefined>(undefined)
  const query = useQuery<PhotoAnalysis | null>({
    queryKey: ['photo-analysis', photoId],
    queryFn: async () => {
      try {
        return await apiGet(`/photos/${photoId}/analysis`)
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) {
          return null
        }
        throw err
      }
    },
    enabled: photoId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === 'pending' || status === 'analyzing') {
        return 2000
      }
      if (sharedMeal && query.state.data === null) {
        return 3000
      }
      return false
    },
  })

  // Auto-confirm in the background no longer goes through useConfirmAnalysis, so
  // refresh the entry (photo_signal) when analysis first reaches confirmed.
  useEffect(() => {
    const status = query.data?.status
    if (status === 'confirmed' && prevStatusRef.current !== 'confirmed') {
      queryClient.invalidateQueries({ queryKey: ['entry'] })
    }
    prevStatusRef.current = status
  }, [query.data?.status, queryClient])

  return query
}

export function useConfirmAnalysis() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (photoId: number) => apiPut(`/photos/${photoId}/analysis/confirm`, {}),
    onSuccess: (_data, photoId) => {
      queryClient.invalidateQueries({ queryKey: ['photo-analysis', photoId] })
      queryClient.invalidateQueries({ queryKey: ['entry'] })
    },
  })
}

export function useRetryAnalysis() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (photoId: number) => apiPut(`/photos/${photoId}/analysis/retry`, {}),
    onSuccess: (_data, photoId) => {
      queryClient.invalidateQueries({ queryKey: ['photo-analysis', photoId] })
    },
  })
}

export function useUpdateIngredient() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ ingredientId, data }: { ingredientId: number; data: Record<string, unknown> }) =>
      apiPut(`/ingredients/${ingredientId}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['photo-analysis'] })
      queryClient.invalidateQueries({ queryKey: ['entry'] })
    },
  })
}

export function useAddIngredient() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ photoId, name }: { photoId: number; name: string }) =>
      apiPost(`/photos/${photoId}/analysis/ingredients`, { name }),
    onSuccess: (_data, { photoId }) => {
      queryClient.invalidateQueries({ queryKey: ['photo-analysis', photoId] })
      queryClient.invalidateQueries({ queryKey: ['entry'] })
    },
  })
}

export function useDeleteIngredient() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (ingredientId: number) => apiDelete(`/ingredients/${ingredientId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['photo-analysis'] })
      queryClient.invalidateQueries({ queryKey: ['entry'] })
    },
  })
}

'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  apiGet,
  apiPost,
  apiPut,
  apiPatch,
  apiDelete,
  apiPostForm,
  ApiError,
} from './client'
import type {
  Entry,
  EntryCreate,
  AuthUser,
  WeatherDailySummary,
  HealthMetricResponse,
  EnrichedDayResponse,
  SupplementCatalogItem,
  PhotoAnalysis,
  Treatment,
  TreatmentCreate,
  TreatmentUpdate,
} from './types'

export function useAuth() {
  return useQuery<AuthUser>({
    queryKey: ['auth'],
    queryFn: () => apiGet('/auth/me'),
    retry: false,
  })
}

export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (pin: string) => apiPost('/auth/login', { pin }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['auth'] })
    },
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
  return useQuery<Entry>({
    queryKey: ['entry', date],
    queryFn: () => apiGet(`/entries/${date}`),
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

export function useUploadPhoto() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ date, file, label }: { date: string; file: File; label?: string }) => {
      const formData = new FormData()
      formData.append('file', file)
      if (label) {
        formData.append('label', label)
      }
      return apiPostForm(`/entries/${date}/photos`, formData)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entry'] })
      queryClient.invalidateQueries({ queryKey: ['entries'] })
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
    },
  })
}

export function useWeatherSummary(date: string) {
  return useQuery<WeatherDailySummary>({
    queryKey: ['weather', date],
    queryFn: () => apiGet(`/weather/${date}`),
    enabled: !!date,
    retry: false,
  })
}

export function useHealthMetrics(date: string) {
  return useQuery<HealthMetricResponse>({
    queryKey: ['health-metrics', date],
    queryFn: () => apiGet(`/health-metrics/${date}`),
    enabled: !!date,
    retry: false,
  })
}

export function useEnrichedDay(date: string) {
  return useQuery<EnrichedDayResponse>({
    queryKey: ['enriched', date],
    queryFn: () => apiGet(`/enriched/${date}`),
    enabled: !!date,
    retry: false,
  })
}

export function useSupplementCatalog(includeArchived = false) {
  const params = includeArchived ? '?include_archived=true' : ''
  return useQuery<SupplementCatalogItem[]>({
    queryKey: ['supplement-catalog', includeArchived],
    queryFn: () => apiGet(`/supplements/catalog${params}`),
  })
}

export function useAddSupplementCatalogItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { key: string; label: string }) =>
      apiPost('/supplements/catalog', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['supplement-catalog'] })
    },
  })
}

export function useUpdateSupplementCatalogItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      key,
      data,
    }: {
      key: string
      data: { label?: string; archived?: boolean; sort_order?: number }
    }) => apiPatch(`/supplements/catalog/${key}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['supplement-catalog'] })
    },
  })
}

export function useTriggerWeatherFetch() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiPost('/weather/fetch', {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['weather'] })
      queryClient.invalidateQueries({ queryKey: ['enriched'] })
    },
  })
}

export function usePhotoAnalysis(photoId: number | null) {
  return useQuery<PhotoAnalysis | null>({
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
      return false
    },
  })
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
    },
  })
}

export function useDeleteIngredient() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (ingredientId: number) => apiDelete(`/ingredients/${ingredientId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['photo-analysis'] })
    },
  })
}

export function useTreatments(activeOn?: string) {
  const params = activeOn ? `?active_on=${activeOn}` : ''
  return useQuery<Treatment[]>({
    queryKey: ['treatments', activeOn ?? 'all'],
    queryFn: () => apiGet(`/treatments${params}`),
  })
}

export function useTreatment(id: number | null) {
  return useQuery<Treatment>({
    queryKey: ['treatment', id],
    queryFn: () => apiGet(`/treatments/${id}`),
    enabled: id !== null,
  })
}

export function useCreateTreatment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: TreatmentCreate) => apiPost('/treatments', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['treatments'] })
    },
  })
}

export function useUpdateTreatment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: TreatmentUpdate }) =>
      apiPut(`/treatments/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['treatments'] })
      queryClient.invalidateQueries({ queryKey: ['treatment'] })
    },
  })
}

export function useDeleteTreatment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => apiDelete(`/treatments/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['treatments'] })
      queryClient.invalidateQueries({ queryKey: ['treatment'] })
    },
  })
}

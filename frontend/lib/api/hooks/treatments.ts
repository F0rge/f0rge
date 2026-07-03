'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPut, apiDelete } from '../client'
import type { Treatment, TreatmentCreate, TreatmentUpdate } from '../types'

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

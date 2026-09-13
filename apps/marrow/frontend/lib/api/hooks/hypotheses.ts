'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPut } from '@f0rge/ui/api'
import type { Hypothesis, HypothesisCreate, HypothesisUpdate, NOf1Slot, NOf1Upsert } from '../types'

export function useHypotheses(status?: Hypothesis['status']) {
  const params = status ? `?status=${status}` : ''
  return useQuery<Hypothesis[]>({
    queryKey: ['hypotheses', status ?? 'all'],
    queryFn: () => apiGet(`/hypotheses${params}`),
  })
}

export function useCreateHypothesis() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: HypothesisCreate) => apiPost('/hypotheses', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hypotheses'] })
    },
  })
}

export function useUpdateHypothesis() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: HypothesisUpdate }) =>
      apiPut(`/hypotheses/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hypotheses'] })
    },
  })
}

export function useNOf1() {
  return useQuery<NOf1Slot | null>({
    queryKey: ['n-of-1'],
    queryFn: () => apiGet('/hypotheses/n-of-1'),
  })
}

export function useUpdateNOf1() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: NOf1Upsert) => apiPut('/hypotheses/n-of-1', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['n-of-1'] })
    },
  })
}

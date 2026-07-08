'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPut, apiDelete, handleMutationError } from '../client'
import type {
  Treatment,
  TreatmentCreate,
  TreatmentUpdate,
  ProtocolResponse,
  TreatmentLogResponse,
} from '../types'

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

export function useProtocol(date: string) {
  return useQuery<ProtocolResponse>({
    queryKey: ['protocol', date],
    queryFn: () => apiGet(`/treatments/protocol?date=${date}`),
    enabled: !!date,
  })
}

export function useLogDose(date: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, dosesTaken }: { id: number; dosesTaken: number }) =>
      apiPut(`/treatments/${id}/log`, { date, doses_taken: dosesTaken }) as Promise<TreatmentLogResponse>,
    onMutate: async ({ id, dosesTaken }) => {
      await queryClient.cancelQueries({ queryKey: ['protocol', date] })
      const prev = queryClient.getQueryData<ProtocolResponse>(['protocol', date])
      queryClient.setQueryData<ProtocolResponse>(['protocol', date], (old) => {
        if (!old) return old
        const items = old.items.map((item) =>
          item.id === id
            ? { ...item, doses_taken: Math.max(0, Math.min(dosesTaken, item.doses_per_day ?? 0)) }
            : item,
        )
        const dosesTakenSum = items
          .filter((item) => item.doses_per_day !== null)
          .reduce((sum, item) => sum + item.doses_taken, 0)
        const dosesPlanned = old.today.doses_planned
        return {
          ...old,
          items,
          today: {
            doses_taken: dosesTakenSum,
            doses_planned: dosesPlanned,
            pct: dosesPlanned > 0 ? dosesTakenSum / dosesPlanned : 0,
          },
        }
      })
      return { prev }
    },
    onError: (err, _vars, context) => {
      if (context?.prev !== undefined) {
        queryClient.setQueryData(['protocol', date], context.prev)
      }
      handleMutationError(err, 'Failed to log dose. Please try again.')
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['protocol', date] })
    },
  })
}

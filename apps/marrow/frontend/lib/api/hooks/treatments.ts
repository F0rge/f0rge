'use client'

import { useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPut, apiDelete, handleMutationError } from '@f0rge/ui/api'
import type {
  Treatment,
  TreatmentCreate,
  TreatmentUpdate,
  ProtocolResponse,
  TreatmentLogResult,
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
  const latestMutationSeq = useRef(0)
  return useMutation({
    mutationFn: ({ id, dosesTaken }: { id: number; dosesTaken: number }) =>
      apiPut(`/treatments/${id}/log`, { date, doses_taken: dosesTaken }) as Promise<TreatmentLogResult>,
    onMutate: async ({ id, dosesTaken }) => {
      const seq = ++latestMutationSeq.current
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
        const wasTodayComplete =
          dosesPlanned > 0 && old.today.doses_taken >= dosesPlanned
        const isTodayComplete = dosesPlanned > 0 && dosesTakenSum >= dosesPlanned
        let streak = old.streak
        let best_streak = old.best_streak
        if (wasTodayComplete && !isTodayComplete) {
          streak = Math.max(0, streak - 1)
          best_streak = old.streak === old.best_streak ? streak : old.best_streak
        } else if (!wasTodayComplete && isTodayComplete) {
          streak = streak + 1
          best_streak = Math.max(best_streak, streak)
        }
        return {
          ...old,
          items,
          today: {
            doses_taken: dosesTakenSum,
            doses_planned: dosesPlanned,
            pct: dosesPlanned > 0 ? dosesTakenSum / dosesPlanned : 0,
          },
          streak,
          best_streak,
        }
      })
      return { prev, seq }
    },
    onSuccess: (result, _vars, context) => {
      if (context?.seq !== latestMutationSeq.current) return
      queryClient.setQueryData<ProtocolResponse>(['protocol', date], (old) => {
        if (!old) return old
        return {
          ...old,
          today: result.today,
          streak: result.streak,
          best_streak: result.best_streak,
        }
      })
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

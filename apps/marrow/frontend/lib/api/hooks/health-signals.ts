'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost } from '@f0rge/ui/api'
import type { WeatherDailySummary, HealthMetricResponse, EnrichedDayResponse } from '../types'

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

'use client'

import { useQuery } from '@tanstack/react-query'
import { apiGet } from '@f0rge/ui/api'
import type {
  TrendsResponse,
  CorrelatesResponse,
  TreatmentResponseList,
  SleepNextDayResponse,
} from '../types'

export function useInsightsTrends(start: string, end: string) {
  return useQuery<TrendsResponse>({
    queryKey: ['insights-trends', start, end],
    queryFn: () => apiGet(`/insights/trends?start=${start}&end=${end}`),
    enabled: !!start && !!end,
  })
}

export function useInsightsCorrelates(
  outcome: string,
  start: string,
  end: string,
  category?: string,
) {
  const params = new URLSearchParams({ outcome, start, end, min_n: '10' })
  if (category && category !== 'all') params.set('category', category)
  return useQuery<CorrelatesResponse>({
    queryKey: ['insights-correlates', outcome, start, end, category ?? 'all'],
    queryFn: () => apiGet(`/insights/correlates?${params.toString()}`),
    enabled: !!outcome && !!start && !!end,
  })
}

export function useInsightsTreatmentResponse(outcome: string) {
  return useQuery<TreatmentResponseList>({
    queryKey: ['insights-treatment-response', outcome],
    queryFn: () => apiGet(`/insights/treatment-response?outcome=${outcome}`),
    enabled: !!outcome,
  })
}

export function useInsightsSleepNextDay(
  outcome: string,
  metric: string,
  start: string,
  end: string,
) {
  return useQuery<SleepNextDayResponse>({
    queryKey: ['insights-sleep-next-day', outcome, metric, start, end],
    queryFn: () =>
      apiGet(
        `/insights/sleep-next-day?outcome=${outcome}&metric=${metric}&start=${start}&end=${end}`,
      ),
    enabled: !!outcome && !!metric && !!start && !!end,
  })
}

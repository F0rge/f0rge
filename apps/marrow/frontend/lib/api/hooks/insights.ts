'use client'

import { useQuery } from '@tanstack/react-query'
import { apiGet } from '@f0rge/ui/api'
import type { TrendsResponse, TreatmentResponseList } from '../types'

export function useInsightsTrends(start: string, end: string) {
  return useQuery<TrendsResponse>({
    queryKey: ['insights-trends', start, end],
    queryFn: () => apiGet(`/insights/trends?start=${start}&end=${end}`),
    enabled: !!start && !!end,
  })
}

export function useInsightsTreatmentResponse(outcome: string) {
  return useQuery<TreatmentResponseList>({
    queryKey: ['insights-treatment-response', outcome],
    queryFn: () => apiGet(`/insights/treatment-response?outcome=${outcome}`),
    enabled: !!outcome,
  })
}

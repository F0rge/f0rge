'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost } from '@f0rge/ui/api'
import type { CatalogSetupRequest, CatalogSuggestions } from '../types/onboarding'

export function useCatalogSuggestions(enabled = true) {
  return useQuery<CatalogSuggestions>({
    queryKey: ['catalog-suggestions'],
    queryFn: () => apiGet('/catalog/suggestions'),
    enabled,
    staleTime: Infinity,
  })
}

export function useSetupCatalogs() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CatalogSetupRequest) =>
      apiPost('/onboarding/catalog-setup', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['symptom-catalog'] })
      queryClient.invalidateQueries({ queryKey: ['supplement-catalog'] })
      queryClient.invalidateQueries({ queryKey: ['medication-catalog'] })
      queryClient.invalidateQueries({ queryKey: ['trackers'] })
    },
  })
}

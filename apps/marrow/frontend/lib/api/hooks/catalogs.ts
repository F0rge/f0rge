'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPatch } from '@f0rge/ui/api'
import type {
  SupplementCatalogItem,
  MedicationCatalogItem,
  DietTagCatalogItem,
  SymptomCatalogItem,
} from '../types'

export function useSupplementCatalog(includeArchived = false) {
  const params = includeArchived ? '?include_archived=true' : ''
  return useQuery<SupplementCatalogItem[]>({
    queryKey: ['supplement-catalog', includeArchived],
    queryFn: () => apiGet(`/supplements/catalog${params}`),
    staleTime: Infinity,
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

export function useMedicationCatalog(includeArchived = false) {
  const params = includeArchived ? '?include_archived=true' : ''
  return useQuery<MedicationCatalogItem[]>({
    queryKey: ['medication-catalog', includeArchived],
    queryFn: () => apiGet(`/medications/catalog${params}`),
    staleTime: Infinity,
  })
}

export function useAddMedicationCatalogItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { key: string; label: string }) =>
      apiPost('/medications/catalog', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['medication-catalog'] })
    },
  })
}

export function useUpdateMedicationCatalogItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      key,
      data,
    }: {
      key: string
      data: { label?: string; archived?: boolean; sort_order?: number }
    }) => apiPatch(`/medications/catalog/${key}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['medication-catalog'] })
    },
  })
}

export function useDietTagCatalog(includeArchived = false) {
  const params = includeArchived ? '?include_archived=true' : ''
  return useQuery<DietTagCatalogItem[]>({
    queryKey: ['diet-tag-catalog', includeArchived],
    queryFn: () => apiGet(`/diet-tags/catalog${params}`),
    staleTime: Infinity,
  })
}

export function useUpdateDietTagCatalogItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      key,
      data,
    }: {
      key: string
      data: { label?: string; archived?: boolean; sort_order?: number }
    }) => apiPatch(`/diet-tags/catalog/${key}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['diet-tag-catalog'] })
    },
  })
}

export function useSymptomCatalog(includeArchived = false) {
  const params = includeArchived ? '?include_archived=true' : ''
  return useQuery<SymptomCatalogItem[]>({
    queryKey: ['symptom-catalog', includeArchived],
    queryFn: () => apiGet(`/symptoms/catalog${params}`),
    staleTime: Infinity,
  })
}

export function useAddSymptomCatalogItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: { key: string; label: string }) =>
      apiPost('/symptoms/catalog', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['symptom-catalog'] })
    },
  })
}

export function useUpdateSymptomCatalogItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      key,
      data,
    }: {
      key: string
      data: { label?: string; archived?: boolean; sort_order?: number }
    }) => apiPatch(`/symptoms/catalog/${key}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['symptom-catalog'] })
    },
  })
}

export function useReorderSymptomCatalog() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (order: string[]) => apiPatch('/symptoms/catalog/reorder', { order }),
    onMutate: async (order: string[]) => {
      await queryClient.cancelQueries({ queryKey: ['symptom-catalog'] })
      const snapshots: { key: readonly unknown[]; data: SymptomCatalogItem[] | undefined }[] = []
      const queries = queryClient.getQueriesData<SymptomCatalogItem[]>({ queryKey: ['symptom-catalog'] })
      for (const [key, data] of queries) {
        snapshots.push({ key, data })
        if (!data) continue
        const byKey = new Map(data.map((s) => [s.key, s]))
        const reordered = order
          .map((k) => byKey.get(k))
          .filter((s): s is SymptomCatalogItem => s !== undefined)
        const remaining = data.filter((s) => !order.includes(s.key))
        queryClient.setQueryData<SymptomCatalogItem[]>(key, [...remaining, ...reordered])
      }
      return { snapshots }
    },
    onError: (_err, _order, context) => {
      context?.snapshots.forEach(({ key, data }) => queryClient.setQueryData(key, data))
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['symptom-catalog'] }),
  })
}

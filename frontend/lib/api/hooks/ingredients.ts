'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiDelete, apiGet, apiPatch, apiPost } from '../client'
import type {
  DietaryIngredient,
  IngredientCreatePayload,
  IngredientUpdatePayload,
} from '../types'

const INGREDIENTS_KEY = ['dietary-ingredients'] as const

export function useIngredientCatalog(search: string, includeArchived: boolean) {
  const params = new URLSearchParams()
  if (search.trim()) params.set('search', search.trim())
  if (includeArchived) params.set('include_archived', 'true')
  const qs = params.toString()
  return useQuery<DietaryIngredient[]>({
    queryKey: ['dietary-ingredients', search.trim(), includeArchived],
    queryFn: () => apiGet(`/dietary-ingredients${qs ? `?${qs}` : ''}`),
  })
}

export function useAddDietaryIngredient() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: IngredientCreatePayload) => apiPost('/dietary-ingredients', data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: INGREDIENTS_KEY }),
  })
}

export function useUpdateDietaryIngredient() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: IngredientUpdatePayload }) =>
      apiPatch(`/dietary-ingredients/${id}`, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: INGREDIENTS_KEY }),
  })
}

export function useArchiveDietaryIngredient() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, archived }: { id: number; archived: boolean }) =>
      apiPatch(`/dietary-ingredients/${id}`, { archived }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: INGREDIENTS_KEY }),
  })
}

export function useAddIngredientAlias() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, alias }: { id: number; alias: string }) =>
      apiPost(`/dietary-ingredients/${id}/aliases`, { alias }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: INGREDIENTS_KEY }),
  })
}

export function useRemoveIngredientAlias() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (aliasId: number) => apiDelete(`/dietary-ingredients/aliases/${aliasId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: INGREDIENTS_KEY }),
  })
}

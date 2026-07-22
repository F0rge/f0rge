'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPut, ApiError } from '@f0rge/ui/api'
import type {
  UserSettings,
  LLMSettingsUpdate,
  EmbeddingSettingsUpdate,
  TaggedMealModeUpdate,
  ProfileTagFilterUpdate,
  CheckinDefaultsUpdate,
  TestConnectionResponse,
  ExternalTokenResponse,
} from '../types'

export function useUserSettings(options?: { enabled?: boolean }) {
  return useQuery<UserSettings>({
    queryKey: ['settings'],
    queryFn: () => apiGet('/settings'),
    enabled: options?.enabled ?? true,
    retry: false,
  })
}

export function useUpdateLLMSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: LLMSettingsUpdate) => apiPut('/settings/llm', data) as Promise<UserSettings>,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
    },
  })
}

export function useUpdateEmbeddingSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: EmbeddingSettingsUpdate) =>
      apiPut('/settings/embedding', data) as Promise<UserSettings>,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
    },
  })
}

export function useUpdateTaggedMealMode() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: TaggedMealModeUpdate) =>
      apiPut('/settings/tagged-meal-mode', data) as Promise<UserSettings>,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
    },
  })
}

export function useUpdateProfileTagFilter() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ProfileTagFilterUpdate) =>
      apiPut('/settings/profile-tag-filter', data) as Promise<UserSettings>,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      // The profile feed is filtered by this rule server-side.
      queryClient.invalidateQueries({ queryKey: ['photos'] })
    },
  })
}

export function useUpdateCheckinDefaults() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CheckinDefaultsUpdate) =>
      apiPut('/settings/checkin-defaults', data) as Promise<UserSettings>,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
    },
  })
}

export function useTestLLMConnection() {
  return useMutation({
    mutationFn: () => apiPost('/settings/llm/test', {}) as Promise<TestConnectionResponse>,
  })
}

export function useTestEmbeddingConnection() {
  return useMutation({
    mutationFn: () =>
      apiPost('/settings/embedding/test', {}) as Promise<TestConnectionResponse>,
  })
}

export function useRegenerateExternalToken() {
  const queryClient = useQueryClient()
  return useMutation<ExternalTokenResponse, ApiError, void>({
    mutationFn: () => apiPost('/settings/external-token/regenerate', {}) as Promise<ExternalTokenResponse>,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
    },
  })
}

export function useRevokeExternalToken() {
  const queryClient = useQueryClient()
  return useMutation<UserSettings, ApiError, void>({
    mutationFn: () => apiPost('/settings/external-token/revoke', {}) as Promise<UserSettings>,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
    },
  })
}

export function useCompleteOnboarding() {
  const queryClient = useQueryClient()
  return useMutation<UserSettings, ApiError, void>({
    mutationFn: () => apiPost('/settings/onboarding/complete', {}) as Promise<UserSettings>,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
    },
  })
}

'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, apiPut, apiDelete, apiPostForm } from './client'
import type { Entry, EntryCreate, AuthUser } from './types'

export function useAuth() {
  return useQuery<AuthUser>({
    queryKey: ['auth'],
    queryFn: () => apiGet('/auth/me'),
    retry: false,
  })
}

export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (pin: string) => apiPost('/auth/login', { pin }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['auth'] })
    },
  })
}

export function useEntries(month?: string) {
  const params = month ? `?month=${month}` : ''
  return useQuery<Entry[]>({
    queryKey: ['entries', month ?? 'all'],
    queryFn: () => apiGet(`/entries${params}`),
  })
}

export function useEntry(date: string) {
  return useQuery<Entry>({
    queryKey: ['entry', date],
    queryFn: () => apiGet(`/entries/${date}`),
    enabled: !!date,
    retry: false,
  })
}

export function useCreateEntry() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: EntryCreate) => apiPost('/entries', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entries'] })
      queryClient.invalidateQueries({ queryKey: ['entry'] })
    },
  })
}

export function useUpdateEntry() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ date, data }: { date: string; data: EntryCreate }) =>
      apiPut(`/entries/${date}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entries'] })
      queryClient.invalidateQueries({ queryKey: ['entry'] })
    },
  })
}

export function useDeleteEntry() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (date: string) => apiDelete(`/entries/${date}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entries'] })
      queryClient.invalidateQueries({ queryKey: ['entry'] })
    },
  })
}

export function useUploadPhoto() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ date, file, label }: { date: string; file: File; label?: string }) => {
      const formData = new FormData()
      formData.append('file', file)
      if (label) {
        formData.append('label', label)
      }
      return apiPostForm(`/entries/${date}/photos`, formData)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entry'] })
      queryClient.invalidateQueries({ queryKey: ['entries'] })
    },
  })
}

export function useDeletePhoto() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => apiDelete(`/photos/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['entry'] })
      queryClient.invalidateQueries({ queryKey: ['entries'] })
    },
  })
}

'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPatch, apiPost, apiDelete, apiPostForm } from '@f0rge/ui/api'
import type { Account, AccountUpdate, ChangePasswordRequest, DeleteAccountRequest } from '../types'

export function useAccount() {
  return useQuery<Account>({
    queryKey: ['account'],
    queryFn: () => apiGet('/account'),
  })
}

export function useAvatarCacheBust() {
  return useQuery<number>({
    queryKey: ['avatar-bust'],
    queryFn: () => 0,
    staleTime: Infinity,
    initialData: 0,
  })
}

export function useUpdateAccount() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: AccountUpdate) => apiPatch('/account', data) as Promise<Account>,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['account'] })
    },
  })
}

export function useUploadAvatar() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      return apiPostForm('/account/avatar', formData) as Promise<Account>
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['account'] })
      queryClient.setQueryData(['avatar-bust'], Date.now())
    },
  })
}

export function useDeleteAvatar() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiDelete('/account/avatar') as Promise<Account>,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['account'] })
      queryClient.setQueryData(['avatar-bust'], Date.now())
    },
  })
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (data: ChangePasswordRequest) => apiPost('/account/password', data) as Promise<void>,
  })
}

export function useDeleteAccount() {
  return useMutation({
    mutationFn: (data: DeleteAccountRequest) => apiDelete('/account', data) as Promise<void>,
  })
}

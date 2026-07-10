'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPatch, apiPost, apiDelete } from '../client'
import type { Account, AccountUpdate, ChangePasswordRequest, DeleteAccountRequest } from '../types'

export function useAccount() {
  return useQuery<Account>({
    queryKey: ['account'],
    queryFn: () => apiGet('/account'),
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

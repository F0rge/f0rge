'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost } from '../client'
import type { AuthUser } from '../types'

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

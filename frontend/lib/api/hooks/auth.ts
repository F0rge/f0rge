'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost } from '../client'
import type { AuthUser, LoginCredentials, SignupCredentials } from '../types'

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
    mutationFn: (credentials: LoginCredentials) => apiPost('/auth/login', credentials),
    onSuccess: () => {
      queryClient.clear()
    },
  })
}

export function useSignup() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (credentials: SignupCredentials) => apiPost('/auth/signup', credentials),
    onSuccess: () => {
      queryClient.clear()
    },
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => apiPost('/auth/logout', {}),
    onSuccess: () => {
      queryClient.clear()
    },
  })
}

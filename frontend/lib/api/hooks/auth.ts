'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiGet, apiPost, ApiError } from '../client'
import type { AuthUser, LoginCredentials, SignupCredentials } from '../types'

const UNAUTHENTICATED: AuthUser = { authenticated: false }

export function useAuth() {
  return useQuery<AuthUser>({
    queryKey: ['auth'],
    queryFn: async () => {
      try {
        return await apiGet('/auth/me')
      } catch (err) {
        // 401 is the normal logged-out state — don't leave stale authenticated:true
        // in cache (react-query keeps previous data on error) or SessionGuard loops.
        if (err instanceof ApiError && err.status === 401) {
          return UNAUTHENTICATED
        }
        throw err
      }
    },
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

'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useTheme } from 'next-themes'
import { useState } from 'react'
import { UiProvider } from '@f0rge/ui'
import { SessionGuard } from '@/components/auth/session-guard'
import { OnboardingProvider } from '@/components/onboarding/onboarding-provider'
import { ThemeProvider } from '@/components/theme-provider'

function ThemedUiProvider({ children }: { children: React.ReactNode }) {
  const { resolvedTheme } = useTheme()
  return (
    <UiProvider colorScheme={resolvedTheme === 'dark' ? 'dark' : 'light'}>
      {children}
    </UiProvider>
  )
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            refetchOnWindowFocus: false,
          },
        },
      })
  )

  return (
    <ThemeProvider>
      <ThemedUiProvider>
        <QueryClientProvider client={queryClient}>
          <SessionGuard>
            <OnboardingProvider>
              {children}
            </OnboardingProvider>
          </SessionGuard>
        </QueryClientProvider>
      </ThemedUiProvider>
    </ThemeProvider>
  )
}

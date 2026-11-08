'use client'

import { focusManager, QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useTheme } from 'next-themes'
import { useEffect, useState } from 'react'
import { UiProvider } from '@f0rge/ui'
import { SessionGuard } from '@/components/auth/session-guard'
import { OnboardingProvider } from '@/components/onboarding/onboarding-provider'
import { ThemeProvider } from '@/components/theme-provider'
import { bindDocumentReturnEvents } from '@/lib/api/day-entry-query'

function ThemedUiProvider({ children }: { children: React.ReactNode }) {
  const { resolvedTheme } = useTheme()
  return (
    <UiProvider colorScheme={resolvedTheme === 'dark' ? 'dark' : 'light'}>
      {children}
    </UiProvider>
  )
}

function DocumentReturnFocus() {
  useEffect(() => {
    // Per-query flags still decide who refetches. useEntry opts in; everyone else stays off.
    focusManager.setEventListener((handleFocus) =>
      bindDocumentReturnEvents(() => {
        handleFocus()
      }),
    )
  }, [])
  return null
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
          <DocumentReturnFocus />
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

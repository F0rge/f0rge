'use client'

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { useCatalogSuggestions, useSetupCatalogs } from '@/lib/api/hooks/onboarding'
import type { CatalogSetupRequest } from '@/lib/api/types/onboarding'
import type { SetupKind } from './tour-steps'

interface OnboardingSetupContextValue {
  selections: CatalogSetupRequest
  setSelection: (kind: SetupKind, values: string[]) => void
  persistSetup: () => Promise<void>
  isPersisting: boolean
  persistError: string | null
  getItemsForKind: (kind: SetupKind) => Array<{ id: string; label: string }>
  isLoadingSuggestions: boolean
}

const OnboardingSetupContext = createContext<OnboardingSetupContextValue | null>(null)

const EMPTY_SELECTIONS: CatalogSetupRequest = {
  symptoms: [],
  medications: [],
  supplements: [],
  trackers: [],
}

export function OnboardingSetupProvider({ children }: { children: ReactNode }) {
  const { data: suggestions, isLoading: isLoadingSuggestions } = useCatalogSuggestions()
  const setupCatalogs = useSetupCatalogs()
  const [selections, setSelections] = useState<CatalogSetupRequest>(EMPTY_SELECTIONS)
  const [persistError, setPersistError] = useState<string | null>(null)

  const setSelection = useCallback((kind: SetupKind, values: string[]) => {
    setSelections((current) => ({ ...current, [kind]: values }))
  }, [])

  const getItemsForKind = useCallback(
    (kind: SetupKind): Array<{ id: string; label: string }> => {
      if (!suggestions) return []
      if (kind === 'trackers') {
        return suggestions.trackers.map((tracker) => ({
          id: tracker.name,
          label: tracker.name,
        }))
      }
      const list = suggestions[kind]
      return list.map((item) => ({ id: item.key, label: item.label }))
    },
    [suggestions],
  )

  const persistSetup = useCallback(async () => {
    setPersistError(null)
    try {
      await setupCatalogs.mutateAsync(selections)
    } catch (error) {
      const message =
        error instanceof Error ? error.message : 'Failed to save your selections'
      setPersistError(message)
      throw error
    }
  }, [selections, setupCatalogs])

  const value = useMemo(
    () => ({
      selections,
      setSelection,
      persistSetup,
      isPersisting: setupCatalogs.isPending,
      persistError,
      getItemsForKind,
      isLoadingSuggestions,
    }),
    [
      selections,
      setSelection,
      persistSetup,
      setupCatalogs.isPending,
      persistError,
      getItemsForKind,
      isLoadingSuggestions,
    ],
  )

  return (
    <OnboardingSetupContext.Provider value={value}>
      {children}
    </OnboardingSetupContext.Provider>
  )
}

export function useOnboardingSetup(): OnboardingSetupContextValue {
  const context = useContext(OnboardingSetupContext)
  if (!context) {
    throw new Error('useOnboardingSetup must be used within OnboardingSetupProvider')
  }
  return context
}

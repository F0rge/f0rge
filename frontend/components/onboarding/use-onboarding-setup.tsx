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

interface PickerItem {
  id: string
  label: string
}

interface OnboardingSetupContextValue {
  selections: CatalogSetupRequest
  setSelection: (kind: SetupKind, values: string[]) => void
  persistSetup: () => Promise<void>
  isPersisting: boolean
  persistError: string | null
  getCuratedItemsForKind: (kind: SetupKind) => PickerItem[]
  getSearchableItemsForKind: (kind: SetupKind) => PickerItem[]
  isLoadingSuggestions: boolean
}

const OnboardingSetupContext = createContext<OnboardingSetupContextValue | null>(null)

const EMPTY_SELECTIONS: CatalogSetupRequest = {
  symptoms: [],
  medications: [],
  supplements: [],
  trackers: [],
}

function dedupePickerItems(items: PickerItem[]): PickerItem[] {
  const seen = new Set<string>()
  const result: PickerItem[] = []
  for (const item of items) {
    if (seen.has(item.id)) continue
    seen.add(item.id)
    result.push(item)
  }
  return result
}

function keyLabelItems(items: Array<{ key: string; label: string }>): PickerItem[] {
  return items.map((item) => ({ id: item.key, label: item.label }))
}

function trackerItems(items: Array<{ name: string }>): PickerItem[] {
  return items.map((item) => ({ id: item.name, label: item.name }))
}

export function OnboardingSetupProvider({ children }: { children: ReactNode }) {
  const { data: suggestions, isLoading: isLoadingSuggestions } = useCatalogSuggestions()
  const setupCatalogs = useSetupCatalogs()
  const [selections, setSelections] = useState<CatalogSetupRequest>(EMPTY_SELECTIONS)
  const [persistError, setPersistError] = useState<string | null>(null)

  const setSelection = useCallback((kind: SetupKind, values: string[]) => {
    setSelections((current) => ({ ...current, [kind]: values }))
  }, [])

  const getCuratedItemsForKind = useCallback(
    (kind: SetupKind): PickerItem[] => {
      if (!suggestions) return []
      if (kind === 'trackers') {
        return trackerItems(suggestions.trackers)
      }
      return keyLabelItems(suggestions[kind])
    },
    [suggestions],
  )

  const getSearchableItemsForKind = useCallback(
    (kind: SetupKind): PickerItem[] => {
      if (!suggestions) return []
      if (kind === 'symptoms') {
        return dedupePickerItems([
          ...keyLabelItems(suggestions.symptoms),
          ...keyLabelItems(suggestions.bulk_symptoms),
        ])
      }
      if (kind === 'medications') {
        return dedupePickerItems([
          ...keyLabelItems(suggestions.medications),
          ...keyLabelItems(suggestions.bulk_medications),
        ])
      }
      if (kind === 'supplements') {
        return dedupePickerItems([
          ...keyLabelItems(suggestions.supplements),
          ...keyLabelItems(suggestions.bulk_supplements),
        ])
      }
      return dedupePickerItems([
        ...trackerItems(suggestions.trackers),
        ...trackerItems(suggestions.bulk_trackers),
      ])
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
      getCuratedItemsForKind,
      getSearchableItemsForKind,
      isLoadingSuggestions,
    }),
    [
      selections,
      setSelection,
      persistSetup,
      setupCatalogs.isPending,
      persistError,
      getCuratedItemsForKind,
      getSearchableItemsForKind,
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

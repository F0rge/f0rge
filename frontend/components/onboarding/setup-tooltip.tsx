'use client'

import type { MouseEvent } from 'react'
import type { TooltipRenderProps } from 'react-joyride'
import { SetupSearchPicker } from './setup-search-picker'
import { useOnboardingSetup } from './use-onboarding-setup'
import type { SetupKind } from './tour-steps'

function isSetupKind(value: unknown): value is SetupKind {
  return (
    value === 'symptoms' ||
    value === 'medications' ||
    value === 'supplements' ||
    value === 'trackers'
  )
}

const SEARCH_PLACEHOLDERS: Record<SetupKind, string> = {
  symptoms: 'Search symptoms…',
  medications: 'Search medications…',
  supplements: 'Search supplements…',
  trackers: 'Search daily trackers…',
}

const ADD_LATER_HINTS: Record<SetupKind, string> = {
  symptoms: 'You can add custom symptoms later in Customize → Symptoms.',
  medications: 'You can add custom medications later in Customize → Catalogs.',
  supplements: 'You can add custom supplements later in Customize → Catalogs.',
  trackers: 'You can add custom trackers later in Customize → Trackers.',
}

export function OnboardingTooltip(props: TooltipRenderProps) {
  const {
    backProps,
    continuous,
    index,
    primaryProps,
    skipProps,
    step,
    tooltipProps,
  } = props

  const setupKind = step.data?.setupKind
  const isSetupStep = step.data?.stepType === 'setup' && isSetupKind(setupKind)
  const {
    selections,
    setSelection,
    persistSetup,
    isPersisting,
    persistError,
    getCuratedItemsForKind,
    getSearchableItemsForKind,
    isLoadingSuggestions,
  } = useOnboardingSetup()

  async function handlePrimaryClick(event: MouseEvent<HTMLButtonElement>) {
    if (!isSetupStep) {
      primaryProps.onClick?.(event)
      return
    }

    if (setupKind === 'trackers') {
      try {
        await persistSetup()
      } catch {
        return
      }
    }

    primaryProps.onClick?.(event)
  }

  return (
    <div
      {...tooltipProps}
      className="max-w-md rounded-xl border bg-background p-4 shadow-lg"
    >
      {step.title && <h4 className="mb-2 text-base font-semibold">{step.title}</h4>}

      {isSetupStep ? (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">{step.content}</p>
          <SetupSearchPicker
            curatedItems={getCuratedItemsForKind(setupKind)}
            searchableItems={getSearchableItemsForKind(setupKind)}
            selected={selections[setupKind]}
            onChange={(values) => setSelection(setupKind, values)}
            isLoading={isLoadingSuggestions}
            searchPlaceholder={SEARCH_PLACEHOLDERS[setupKind]}
            addLaterHint={ADD_LATER_HINTS[setupKind]}
          />
          {persistError && (
            <p className="text-sm text-destructive">{persistError}</p>
          )}
        </div>
      ) : (
        <div className="text-sm leading-relaxed">{step.content}</div>
      )}

      <div className="mt-4 flex items-center justify-between gap-2">
        <button
          type="button"
          className="text-sm text-muted-foreground"
          {...skipProps}
        >
          {skipProps.title}
        </button>
        <div className="flex items-center gap-2">
          {index > 0 && (
            <button
              type="button"
              className="rounded-lg border px-3 py-2 text-sm"
              {...backProps}
            >
              {backProps.title}
            </button>
          )}
          {continuous && (
            <button
              type="button"
              className="rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-60"
              {...primaryProps}
              onClick={handlePrimaryClick}
              disabled={isSetupStep && setupKind === 'trackers' && isPersisting}
            >
              {isSetupStep && setupKind === 'trackers' && isPersisting
                ? 'Saving…'
                : primaryProps.title}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

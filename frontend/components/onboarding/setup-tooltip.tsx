'use client'

import type { MouseEvent } from 'react'
import type { TooltipRenderProps } from 'react-joyride'
import { SetupChipPicker } from './setup-chip-picker'
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
    getItemsForKind,
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
          <SetupChipPicker
            items={getItemsForKind(setupKind)}
            selected={selections[setupKind]}
            onChange={(values) => setSelection(setupKind, values)}
            isLoading={isLoadingSuggestions}
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

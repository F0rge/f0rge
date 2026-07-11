'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import {
  ACTIONS,
  EVENTS,
  STATUS,
  defaultLocale,
  useJoyride,
  type EventData,
  type Step,
} from 'react-joyride'
import { useAuth } from '@/lib/api/hooks/auth'
import { useCompleteOnboarding, useUserSettings } from '@/lib/api/hooks/settings'
import { joyrideStyles, joyrideThemeOptions } from './joyride-theme'
import { OnboardingTooltip } from './setup-tooltip'
import { TOUR_STEPS, tourStepsForReplay, type TourStepDefinition } from './tour-steps'
import { OnboardingSetupProvider, useOnboardingSetup } from './use-onboarding-setup'
import { routeMatches, waitForSelector } from './wait-for-target'

interface OnboardingContextValue {
  startTour: (options?: { replay?: boolean }) => void
  isRunning: boolean
}

const OnboardingContext = createContext<OnboardingContextValue | null>(null)

function buildJoyrideSteps(
  definitions: TourStepDefinition[],
  navigate: (route: string) => void,
): Step[] {
  return definitions.map((def) => ({
    target: def.target,
    title: def.title,
    content: def.content,
    placement: def.placement ?? 'bottom',
    isFixed: def.isFixed,
    data: {
      route: def.route,
      stepType: def.stepType ?? 'tour',
      setupKind: def.setupKind,
    },
    before: async () => {
      if (!routeMatches(window.location.pathname, def.route)) {
        navigate(def.route)
      }
      await waitForSelector(def.target)
    },
  }))
}

export function OnboardingProvider({ children }: { children: React.ReactNode }) {
  return (
    <OnboardingSetupProvider>
      <OnboardingTourInner>{children}</OnboardingTourInner>
    </OnboardingSetupProvider>
  )
}

function OnboardingTourInner({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const { data: auth } = useAuth()
  const { data: settings, isLoading: settingsLoading } = useUserSettings({
    enabled: auth?.authenticated === true,
  })
  const completeOnboarding = useCompleteOnboarding()
  const { persistSetup } = useOnboardingSetup()

  const [run, setRun] = useState(false)
  const [stepIndex, setStepIndex] = useState(0)
  const [isReplay, setIsReplay] = useState(false)
  const autoStartedRef = useRef(false)

  const stepDefinitions = isReplay ? tourStepsForReplay() : TOUR_STEPS
  const steps = useMemo(
    () => buildJoyrideSteps(stepDefinitions, (route) => router.push(route)),
    [router, stepDefinitions],
  )

  const finishTour = useCallback(
    async (shouldPersist: boolean) => {
      setRun(false)
      setStepIndex(0)
      if (shouldPersist) {
        try {
          await persistSetup()
          await completeOnboarding.mutateAsync()
        } catch {
          setIsReplay(false)
          return
        }
      }
      setIsReplay(false)
    },
    [completeOnboarding, persistSetup],
  )

  const onEvent = useCallback(
    (data: EventData) => {
      const { type, action, index, status } = data

      if (type === EVENTS.STEP_AFTER) {
        if (action === ACTIONS.NEXT) {
          setStepIndex(index + 1)
        } else if (action === ACTIONS.PREV) {
          setStepIndex(index - 1)
        }
      }

      if (
        type === EVENTS.TOUR_END ||
        status === STATUS.FINISHED ||
        status === STATUS.SKIPPED
      ) {
        void finishTour(!isReplay)
      }
    },
    [finishTour, isReplay],
  )

  const { Tour } = useJoyride({
    run,
    stepIndex,
    steps,
    continuous: true,
    scrollToFirstStep: true,
    onEvent,
    styles: joyrideStyles,
    locale: {
      ...defaultLocale,
      skip: 'Skip tour',
      last: 'Done',
    },
    tooltipComponent: OnboardingTooltip,
    options: {
      ...joyrideThemeOptions,
      showProgress: true,
      skipBeacon: true,
      overlayClickAction: false,
      dismissKeyAction: 'close',
      skipScroll: false,
      spotlightPadding: 8,
    },
  })

  const startTour = useCallback(
    (options?: { replay?: boolean }) => {
      setIsReplay(options?.replay ?? false)
      setStepIndex(0)
      setRun(true)
      if (!routeMatches(pathname, '/checkin')) {
        router.push('/checkin')
      }
    },
    [pathname, router],
  )

  useEffect(() => {
    if (autoStartedRef.current) return
    if (!auth?.authenticated) return
    if (settingsLoading) return
    if (settings?.onboarding_completed) return
    if (pathname.startsWith('/login') || pathname.startsWith('/signup')) return

    let cancelled = false

    const startWhenReady = async () => {
      if (!routeMatches(pathname, '/checkin')) {
        router.push('/checkin')
      }
      await waitForSelector('body', 15000)
      if (!cancelled) {
        autoStartedRef.current = true
        startTour()
      }
    }

    void startWhenReady()

    return () => {
      cancelled = true
    }
  }, [auth?.authenticated, settings?.onboarding_completed, settingsLoading, pathname, router, startTour])

  const value = useMemo(
    () => ({
      startTour,
      isRunning: run,
    }),
    [run, startTour],
  )

  return (
    <OnboardingContext.Provider value={value}>
      {children}
      {Tour}
    </OnboardingContext.Provider>
  )
}

export function useOnboardingTour(): OnboardingContextValue {
  const context = useContext(OnboardingContext)
  if (!context) {
    throw new Error('useOnboardingTour must be used within OnboardingProvider')
  }
  return context
}

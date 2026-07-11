'use client'

import { Compass } from 'lucide-react'
import { useOnboardingTour } from '@/components/onboarding/onboarding-provider'
import { BUTTON_CLASS } from '@/components/settings/constants'

export function OnboardingSection() {
  const { startTour, isRunning } = useOnboardingTour()

  return (
    <div className="rounded-xl border border-border p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Compass className="size-4 text-muted-foreground" />
        <h2 className="font-semibold">App tour</h2>
      </div>
      <p className="text-sm text-muted-foreground">
        Walk through the main features — check-in cards, navigation, customize hub, and more.
      </p>
      <button
        type="button"
        className={BUTTON_CLASS}
        disabled={isRunning}
        onClick={() => startTour({ replay: true })}
      >
        {isRunning ? 'Tour in progress…' : 'Replay app tour'}
      </button>
    </div>
  )
}

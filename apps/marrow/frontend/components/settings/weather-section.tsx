'use client'

import { toast } from 'sonner'
import { Cloud, RefreshCw } from 'lucide-react'
import { useTriggerWeatherFetch } from '@/lib/api/hooks'
import { handleMutationError } from '@f0rge/ui/api'
import { SettingsCard } from './settings-card'

export function WeatherSection() {
  const weatherFetch = useTriggerWeatherFetch()

  const handleWeatherFetch = async () => {
    try {
      await weatherFetch.mutateAsync()
      toast.success('Weather data fetched')
    } catch (err) {
      handleMutationError(err, 'Weather fetch failed — check API key')
    }
  }

  return (
    <SettingsCard icon={Cloud} iconClassName="text-blue-500" title="Weather Data">
      <p className="text-sm text-muted-foreground">
        Fetches hourly from OpenWeatherMap for Luxembourg. Barometric pressure drops correlate with symptom flares.
      </p>
      <button
        type="button"
        onClick={handleWeatherFetch}
        disabled={weatherFetch.isPending}
        className="flex min-h-[44px] w-full items-center justify-center gap-2 rounded-xl border border-border px-4 py-2.5 text-sm font-medium transition-all hover:bg-muted disabled:opacity-50"
      >
        <RefreshCw className={`size-4 ${weatherFetch.isPending ? 'animate-spin' : ''}`} />
        Fetch Now
      </button>
    </SettingsCard>
  )
}

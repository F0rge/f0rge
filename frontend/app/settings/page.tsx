'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { Cloud, Heart, RefreshCw, Upload, ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import { useTriggerWeatherFetch } from '@/lib/api/hooks'
import { apiPostForm } from '@/lib/api/client'

export default function SettingsPage() {
  const weatherFetch = useTriggerWeatherFetch()
  const [uploading, setUploading] = useState(false)

  const handleWeatherFetch = async () => {
    try {
      await weatherFetch.mutateAsync()
      toast.success('Weather data fetched')
    } catch {
      toast.error('Weather fetch failed — check API key')
    }
  }

  const handleXmlUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      await apiPostForm('/health-metrics/import', formData)
      toast.success('Health data imported')
    } catch {
      toast.error('Import failed')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  return (
    <div className="mx-auto max-w-md px-4 py-6">
      <div className="mb-6 flex items-center gap-3">
        <Link href="/checkin" className="text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-5" />
        </Link>
        <h1 className="text-xl font-bold">Settings</h1>
      </div>

      <div className="space-y-6">
        {/* Weather */}
        <div className="rounded-xl border border-border p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Cloud className="size-5 text-blue-500" />
            <h2 className="font-semibold">Weather Data</h2>
          </div>
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
        </div>

        {/* Apple Health */}
        <div className="rounded-xl border border-border p-4 space-y-3">
          <div className="flex items-center gap-2">
            <Heart className="size-5 text-red-500" />
            <h2 className="font-semibold">Apple Health</h2>
          </div>
          <p className="text-sm text-muted-foreground">
            Auto-syncs via Health Auto Export iOS app. Use this upload for manual XML imports as a backup.
          </p>
          <label
            className={`flex min-h-[44px] w-full cursor-pointer items-center justify-center gap-2 rounded-xl border border-border px-4 py-2.5 text-sm font-medium transition-all hover:bg-muted ${uploading ? 'opacity-50' : ''}`}
          >
            <Upload className="size-4" />
            {uploading ? 'Importing...' : 'Upload Apple Health XML'}
            <input
              type="file"
              accept=".xml,.json"
              onChange={handleXmlUpload}
              className="hidden"
              disabled={uploading}
            />
          </label>
        </div>

        {/* Info */}
        <div className="rounded-xl border border-border p-4 space-y-2">
          <h2 className="font-semibold">Data Sources</h2>
          <ul className="space-y-1 text-sm text-muted-foreground">
            <li>Weather: auto-fetches hourly (background)</li>
            <li>Apple Health: auto-syncs via Health Auto Export app</li>
            <li>Check-in: manual daily entry</li>
            <li>Vault sync: every 15 minutes to Obsidian</li>
          </ul>
        </div>
      </div>
    </div>
  )
}

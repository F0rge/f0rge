'use client'

import { ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import { WeatherSection } from '@/components/settings/weather-section'
import { AiProviderSection } from '@/components/settings/ai-provider-section'
import { EmbeddingProviderSection } from '@/components/settings/embedding-provider-section'
import { ExternalTokenSection } from '@/components/settings/external-token-section'
import { AppleHealthSection } from '@/components/settings/apple-health-section'
import { ExportDataSection } from '@/components/settings/export-data-section'
import { DataSourcesSection } from '@/components/settings/data-sources-section'

export default function SettingsPage() {
  return (
    <div className="mx-auto max-w-md px-4 py-6">
      <div className="mb-6 flex items-center gap-3">
        <Link href="/checkin" className="text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-5" />
        </Link>
        <h1 className="text-xl font-bold">Settings</h1>
      </div>

      <div className="space-y-6">
        <WeatherSection />
        <AiProviderSection />
        <EmbeddingProviderSection />
        <ExternalTokenSection />
        <AppleHealthSection />
        <ExportDataSection />
        <DataSourcesSection />
      </div>
    </div>
  )
}

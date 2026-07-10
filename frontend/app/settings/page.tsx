'use client'

import { ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import { PageShell } from '@/components/layout/page-shell'
import { WeatherSection } from '@/components/settings/weather-section'
import { AiProviderSection } from '@/components/settings/ai-provider-section'
import { EmbeddingProviderSection } from '@/components/settings/embedding-provider-section'
import { ExternalTokenSection } from '@/components/settings/external-token-section'
import { AppleHealthSection } from '@/components/settings/apple-health-section'
import { ExportDataSection } from '@/components/settings/export-data-section'
import { DataSourcesSection } from '@/components/settings/data-sources-section'
import { LogoutSection } from '@/components/settings/logout-section'

export default function SettingsPage() {
  return (
    <PageShell className="py-2">
      <div className="mb-6 flex items-center gap-3">
        <Link href="/checkin" className="text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-5" />
        </Link>
        <h1 className="text-xl font-bold">Settings</h1>
      </div>

      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-12 lg:col-span-6">
          <WeatherSection />
        </div>
        <div className="col-span-12 lg:col-span-6">
          <AiProviderSection />
        </div>
        <div className="col-span-12 lg:col-span-6">
          <EmbeddingProviderSection />
        </div>
        <div className="col-span-12 lg:col-span-6">
          <ExternalTokenSection />
        </div>
        <div className="col-span-12 lg:col-span-6">
          <AppleHealthSection />
        </div>
        <div className="col-span-12 lg:col-span-6">
          <ExportDataSection />
        </div>
        <div className="col-span-12">
          <DataSourcesSection />
        </div>
        <div className="col-span-12 lg:col-span-6">
          <LogoutSection />
        </div>
      </div>
    </PageShell>
  )
}

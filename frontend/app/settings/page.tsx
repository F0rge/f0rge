'use client'

import { ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import { PageShell } from '@/components/layout/page-shell'
import { WeatherSection } from '@/components/settings/weather-section'
import { AiSettingsSection } from '@/components/settings/ai-settings-section'
import { ExternalTokenSection } from '@/components/settings/external-token-section'
import { AppleHealthSection } from '@/components/settings/apple-health-section'
import { DataSourcesSection } from '@/components/settings/data-sources-section'

function SettingsGroup({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <section className="space-y-4">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </h2>
      <div className="grid grid-cols-12 gap-6">{children}</div>
    </section>
  )
}

export default function SettingsPage() {
  return (
    <PageShell className="space-y-8 py-2">
      <div className="flex items-center gap-3">
        <Link href="/checkin" className="text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-5" />
        </Link>
        <h1 className="text-xl font-bold">Settings</h1>
      </div>

      <SettingsGroup title="Integrations">
        <div className="col-span-12 lg:col-span-6">
          <WeatherSection />
        </div>
        <div className="col-span-12 lg:col-span-6">
          <ExternalTokenSection />
        </div>
        <div className="col-span-12 lg:col-span-6">
          <AppleHealthSection />
        </div>
      </SettingsGroup>

      <SettingsGroup title="AI">
        <div className="col-span-12">
          <AiSettingsSection />
        </div>
      </SettingsGroup>

      <SettingsGroup title="About">
        <div className="col-span-12">
          <DataSourcesSection />
        </div>
      </SettingsGroup>
    </PageShell>
  )
}

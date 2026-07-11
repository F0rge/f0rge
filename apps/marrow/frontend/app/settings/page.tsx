'use client'

import type { ReactNode } from 'react'
import { ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import { PageShell } from '@/components/layout/page-shell'
import { PageHeader } from '@/components/layout/page-header'
import { WeatherSection } from '@/components/settings/weather-section'
import { AiSettingsSection } from '@/components/settings/ai-settings-section'
import { ExternalTokenSection } from '@/components/settings/external-token-section'
import { AppleHealthSection } from '@/components/settings/apple-health-section'
import { DataSourcesSection } from '@/components/settings/data-sources-section'
import { OnboardingSection } from '@/components/settings/onboarding-section'

function SettingsGroup({
  title,
  children,
}: {
  title: string
  children: ReactNode
}) {
  return (
    <section className="space-y-4">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </h2>
      {children}
    </section>
  )
}

export default function SettingsPage() {
  return (
    <PageShell className="space-y-8 pb-2">
      <PageHeader
        data-tour="settings-page"
        title={
          <div className="flex items-center gap-3">
            <Link href="/checkin" className="text-muted-foreground hover:text-foreground">
              <ArrowLeft className="size-5" />
            </Link>
            <h1 className="text-xl font-bold">Settings</h1>
          </div>
        }
      />

      <SettingsGroup title="Integrations">
        <div className="grid gap-6 lg:grid-cols-2">
          <WeatherSection />
          <AppleHealthSection />
        </div>
        <ExternalTokenSection />
      </SettingsGroup>

      <SettingsGroup title="AI">
        <AiSettingsSection />
      </SettingsGroup>

      <SettingsGroup title="About">
        <DataSourcesSection />
      </SettingsGroup>

      <SettingsGroup title="Help">
        <OnboardingSection />
      </SettingsGroup>
    </PageShell>
  )
}

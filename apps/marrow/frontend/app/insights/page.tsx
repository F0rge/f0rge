'use client'

import { Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { HeaderControls } from '@/components/insights/header-controls'
import { TrendGrid } from '@/components/insights/trend-grid'
import { CorrelatesTable } from '@/components/insights/correlates-table'
import { TreatmentResponse } from '@/components/insights/treatment-response'
import { SleepNextDay } from '@/components/insights/sleep-next-day'
import { PageShell } from '@/components/layout/page-shell'
import { PageHeader } from '@/components/layout/page-header'
import { formatLocalDate as fmt } from '@f0rge/ui'

function getDefaultDates(): { start: string; end: string } {
  const end = new Date()
  const start = new Date()
  start.setDate(end.getDate() - 90)
  return { start: fmt(start), end: fmt(end) }
}

function InsightsContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const defaults = getDefaultDates()
  const start = searchParams.get('start') ?? defaults.start
  const end = searchParams.get('end') ?? defaults.end
  const outcome = searchParams.get('outcome') ?? 'overall'

  function updateFilters(next: { start?: string; end?: string; outcome?: string }) {
    const params = new URLSearchParams(searchParams.toString())
    if (next.start !== undefined) params.set('start', next.start)
    if (next.end !== undefined) params.set('end', next.end)
    if (next.outcome !== undefined) params.set('outcome', next.outcome)
    router.replace(`/insights?${params.toString()}`)
  }

  return (
    <PageShell>
      <PageHeader
        className="mb-4"
        data-tour="insights-header"
        title="Insights"
        subtitle="Analytics & correlations"
      />

      <section className="mb-6">
        <HeaderControls
          start={start}
          end={end}
          outcome={outcome}
          onStartChange={(v) => updateFilters({ start: v })}
          onEndChange={(v) => updateFilters({ end: v })}
          onOutcomeChange={(v) => updateFilters({ outcome: v })}
        />
      </section>

      <div className="grid grid-cols-12 gap-6">
        <section className="col-span-12 lg:col-span-8">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Trends
          </h2>
          <TrendGrid start={start} end={end} />
        </section>

        <section className="col-span-12 lg:col-span-4">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Top Correlates — {outcome}
          </h2>
          <CorrelatesTable outcome={outcome} start={start} end={end} />
        </section>

        <section className="col-span-12 lg:col-span-6">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Treatment Response
          </h2>
          <TreatmentResponse outcome={outcome} />
        </section>

        <section className="col-span-12 lg:col-span-6">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            Sleep vs Next-Day Outcome
          </h2>
          <SleepNextDay outcome={outcome} start={start} end={end} />
        </section>
      </div>
    </PageShell>
  )
}

export default function InsightsPage() {
  return (
    <Suspense>
      <InsightsContent />
    </Suspense>
  )
}

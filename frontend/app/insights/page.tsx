'use client'

import { useState } from 'react'
import { HeaderControls } from '@/components/insights/header-controls'
import { TrendGrid } from '@/components/insights/trend-grid'
import { CorrelatesTable } from '@/components/insights/correlates-table'
import { TreatmentResponse } from '@/components/insights/treatment-response'
import { SleepNextDay } from '@/components/insights/sleep-next-day'
import { formatLocalDate as fmt } from '@/lib/utils'

function getDefaultDates(): { start: string; end: string } {
  const end = new Date()
  const start = new Date()
  start.setDate(end.getDate() - 90)
  return { start: fmt(start), end: fmt(end) }
}

export default function InsightsPage() {
  const defaults = getDefaultDates()
  const [start, setStart] = useState(defaults.start)
  const [end, setEnd] = useState(defaults.end)
  const [outcome, setOutcome] = useState('overall')

  return (
    <div className="mx-auto w-full max-w-lg p-4">
      <div className="mb-4">
        <h1 className="text-xl font-semibold tracking-tight">Insights</h1>
        <p className="text-sm text-muted-foreground">Analytics &amp; correlations</p>
      </div>

      <section className="mb-6">
        <HeaderControls
          start={start}
          end={end}
          outcome={outcome}
          onStartChange={setStart}
          onEndChange={setEnd}
          onOutcomeChange={setOutcome}
        />
      </section>

      <section className="mb-6">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Trends
        </h2>
        <TrendGrid start={start} end={end} />
      </section>

      <section className="mb-6">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Top Correlates — {outcome}
        </h2>
        <CorrelatesTable outcome={outcome} start={start} end={end} />
      </section>

      <section className="mb-6">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Treatment Response
        </h2>
        <TreatmentResponse outcome={outcome} />
      </section>

      <section className="mb-6">
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Sleep vs Next-Day Outcome
        </h2>
        <SleepNextDay outcome={outcome} start={start} end={end} />
      </section>
    </div>
  )
}

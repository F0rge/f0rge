'use client'

import { Suspense, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Tabs, TabsList, TabsTrigger, formatLocalDate as fmt } from '@f0rge/ui'
import { PageShell } from '@/components/layout/page-shell'
import { PageHeader } from '@/components/layout/page-header'
import { SignalsHeaderControls } from '@/components/signals/header-controls'
import { SignalsFetchStatus, SignalsTabPanels } from '@/components/signals/signals-panels'
import { useSignals } from '@/lib/api/hooks/signals'
import type { GoodDirection } from '@/lib/api/types/signals'

type Tab = 'today' | 'drivers' | 'trends'

function getDefaultDates(): { start: string; end: string } {
  const end = new Date()
  const start = new Date()
  start.setDate(end.getDate() - 90)
  return { start: fmt(start), end: fmt(end) }
}

function parseTab(value: string | null): Tab {
  if (value === 'drivers' || value === 'trends') return value
  return 'today'
}

function outcomeGoodDirection(
  trends: { series: { key: string; good_direction: GoodDirection }[] },
  outcome: string,
): GoodDirection {
  const match = trends.series.find((s) => s.key === outcome)
  if (match?.good_direction) return match.good_direction
  if (outcome === 'sick' || outcome.startsWith('sym_')) return 'down'
  return match?.good_direction ?? null
}

function SignalsContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const defaults = getDefaultDates()
  const start = searchParams.get('start') ?? defaults.start
  const end = searchParams.get('end') ?? defaults.end
  const outcome = searchParams.get('outcome') ?? 'overall'
  const tabParam = searchParams.get('tab')
  const tab = parseTab(tabParam)

  const { data, isPending, isFetching, isError, refetch } = useSignals(outcome, start, end)

  function updateParams(next: Record<string, string | undefined>) {
    const params = new URLSearchParams(searchParams.toString())
    for (const [key, value] of Object.entries(next)) {
      if (value === undefined) params.delete(key)
      else params.set(key, value)
    }
    router.replace(`/signals?${params.toString()}`)
  }

  useEffect(() => {
    if (tabParam == null) return
    if (tabParam === 'today' || tabParam === 'drivers' || tabParam === 'trends') return
    const params = new URLSearchParams(searchParams.toString())
    params.set('tab', 'today')
    router.replace(`/signals?${params.toString()}`)
  }, [tabParam, searchParams, router])

  const goodDirection =
    data != null ? outcomeGoodDirection(data.trends, outcome) : null

  return (
    <PageShell>
      <div className="mx-auto w-full max-w-lg">
        <PageHeader
          className="mb-4"
          data-tour="signals-header"
          title="Signals"
          subtitle="What moves your outcomes"
        />

        <section className="mb-4">
          <SignalsHeaderControls
            start={start}
            end={end}
            outcome={outcome}
            onStartChange={(v) => updateParams({ start: v })}
            onEndChange={(v) => updateParams({ end: v })}
            onOutcomeChange={(v) => updateParams({ outcome: v })}
          />
        </section>

        <Tabs
          value={tab}
          onValueChange={(v) => {
            if (v) updateParams({ tab: v })
          }}
          className="gap-4"
        >
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="today">Today</TabsTrigger>
            <TabsTrigger value="drivers">Drivers</TabsTrigger>
            <TabsTrigger value="trends">Trends</TabsTrigger>
          </TabsList>

          <SignalsFetchStatus
            isPending={isPending}
            isFetching={isFetching}
            isError={isError}
            hasData={data != null}
            onRetry={() => refetch()}
          />

          {data && (
            <SignalsTabPanels data={data} goodDirection={goodDirection} />
          )}
        </Tabs>
      </div>
    </PageShell>
  )
}

export default function SignalsPage() {
  return (
    <Suspense>
      <SignalsContent />
    </Suspense>
  )
}

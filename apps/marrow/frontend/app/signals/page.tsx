'use client'

import { Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Loader2 } from 'lucide-react'
import {
  FetchError,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  formatLocalDate as fmt,
} from '@f0rge/ui'
import { PageShell } from '@/components/layout/page-shell'
import { PageHeader } from '@/components/layout/page-header'
import { SignalsHeaderControls } from '@/components/signals/header-controls'
import { InsufficientDataBanner } from '@/components/signals/insufficient-data'
import { TodayWaterfall } from '@/components/signals/today-waterfall'
import { CalibrationStrip } from '@/components/signals/calibration-strip'
import { ModelQuality } from '@/components/signals/model-quality'
import { UnexplainedDays } from '@/components/signals/unexplained-days'
import { DriverCard } from '@/components/signals/driver-card'
import { SetAside } from '@/components/signals/set-aside'
import { SignalsTrendGrid } from '@/components/signals/trend-grid'
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
  const tab = parseTab(searchParams.get('tab'))

  const { data, isPending, isFetching, isError, refetch } = useSignals(outcome, start, end)

  function updateParams(next: Record<string, string | undefined>) {
    const params = new URLSearchParams(searchParams.toString())
    for (const [key, value] of Object.entries(next)) {
      if (value === undefined) params.delete(key)
      else params.set(key, value)
    }
    router.replace(`/signals?${params.toString()}`)
  }

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

          {isPending && !data && (
            <div
              role="status"
              className="flex items-center justify-center py-12"
              aria-label="Loading signals"
            >
              <Loader2 className="size-6 animate-spin text-muted-foreground" />
            </div>
          )}

          {isFetching && data && (
            <p className="text-xs text-muted-foreground" role="status">
              Updating…
            </p>
          )}

          {isError && !data && (
            <FetchError message="Failed to load signals." onRetry={() => refetch()} />
          )}

          {data && (
            <>
              <InsufficientDataBanner meta={data.meta} />

              <TabsContent value="today" className="mt-0 space-y-6">
                {data.meta.insufficient_data ? (
                  <p className="text-sm text-muted-foreground">
                    Today&apos;s breakdown unlocks after more check-ins.
                  </p>
                ) : (
                  <>
                    <TodayWaterfall today={data.today} goodDirection={goodDirection} />
                    <CalibrationStrip series={data.today.calibration_series ?? []} />
                    <ModelQuality model={data.model} />
                    <UnexplainedDays
                      unexplained={data.unexplained}
                      hideRelearning={data.model.relearning}
                    />
                  </>
                )}
              </TabsContent>

              <TabsContent value="drivers" className="mt-0 space-y-4">
                {data.meta.insufficient_data ? (
                  <p className="text-sm text-muted-foreground">
                    Drivers unlock after more check-ins.
                  </p>
                ) : (
                  <>
                    <div className="space-y-2">
                      {data.drivers.length === 0 ? (
                        <p className="text-sm text-muted-foreground">
                          No drivers identified yet.
                        </p>
                      ) : (
                        data.drivers.map((d) => <DriverCard key={d.feature} driver={d} />)
                      )}
                    </div>
                    <SetAside mirrors={data.mirrors} />
                  </>
                )}
              </TabsContent>

              <TabsContent value="trends" className="mt-0">
                <SignalsTrendGrid series={data.trends.series} />
              </TabsContent>
            </>
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

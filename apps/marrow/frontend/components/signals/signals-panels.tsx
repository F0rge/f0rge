import { Loader2 } from 'lucide-react'
import { FetchError, TabsContent } from '@f0rge/ui'
import { InsufficientDataBanner } from '@/components/signals/insufficient-data'
import { TodayWaterfall } from '@/components/signals/today-waterfall'
import { CalibrationStrip } from '@/components/signals/calibration-strip'
import { ModelQuality } from '@/components/signals/model-quality'
import { UnexplainedDays } from '@/components/signals/unexplained-days'
import { DriverCard } from '@/components/signals/driver-card'
import { SetAside } from '@/components/signals/set-aside'
import { SignalsTrendGrid } from '@/components/signals/trend-grid'
import type { GoodDirection, SignalsResponse } from '@/lib/api/types/signals'

interface FetchProps {
  isPending: boolean
  isFetching: boolean
  isError: boolean
  hasData: boolean
  onRetry: () => void
}

export function SignalsFetchStatus({
  isPending,
  isFetching,
  isError,
  hasData,
  onRetry,
}: FetchProps) {
  return (
    <>
      {isPending && !hasData && (
        <div
          role="status"
          className="flex items-center justify-center py-12"
          aria-label="Loading signals"
        >
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      )}
      {isFetching && hasData && (
        <p className="text-xs text-muted-foreground" role="status">
          Updating…
        </p>
      )}
      {isError && hasData && (
        <div
          role="status"
          className="flex items-center justify-between gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-xs text-destructive"
        >
          <span>Couldn&apos;t refresh signals.</span>
          <button
            type="button"
            className="font-medium underline-offset-4 hover:underline"
            onClick={onRetry}
          >
            Retry
          </button>
        </div>
      )}
      {isError && !hasData && (
        <FetchError message="Failed to load signals." onRetry={onRetry} />
      )}
    </>
  )
}

interface PanelsProps {
  data: SignalsResponse
  goodDirection: GoodDirection
}

export function SignalsTabPanels({ data, goodDirection }: PanelsProps) {
  return (
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
  )
}
